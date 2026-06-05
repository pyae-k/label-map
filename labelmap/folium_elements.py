"""Custom Folium MacroElements for connectors, drag sync, and export."""

from folium.elements import MacroElement
from jinja2 import Template

from labelmap.config import CONNECTOR_COLOR, CONNECTOR_OPACITY, LABEL_SAVE_MESSAGE


class DynamicConnectors(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var items = {{ this.items | tojson }};
            var chartRadiusPx = {{ this.chart_radius_px }};
            var layerGroup = L.layerGroup().addTo(map);

            function edgePoints(chartLatLng, labelLatLng, iconW, iconH) {
                var chartPx = map.latLngToContainerPoint(chartLatLng);
                var labelPx = map.latLngToContainerPoint(labelLatLng);
                var boxCx = labelPx.x + iconW / 2;
                var boxCy = labelPx.y + iconH / 2;
                var dx = boxCx - chartPx.x;
                var dy = boxCy - chartPx.y;
                if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
                    return [chartLatLng, labelLatLng];
                }
                var edgeScale = Math.min((iconW / 2) / Math.abs(dx), (iconH / 2) / Math.abs(dy));
                var labelEdgePx = L.point(boxCx - dx * edgeScale, boxCy - dy * edgeScale);
                var dist = Math.hypot(dx, dy) || 1;
                var chartEdgePx = L.point(
                    chartPx.x + dx / dist * chartRadiusPx,
                    chartPx.y + dy / dist * chartRadiusPx
                );
                return [
                    map.containerPointToLatLng(chartEdgePx),
                    map.containerPointToLatLng(labelEdgePx)
                ];
            }

            function updateLines() {
                layerGroup.clearLayers();
                items.forEach(function(item) {
                    var labelMarker = window[item.label_marker_name];
                    if (!labelMarker) return;
                    var pts = edgePoints(
                        L.latLng(item.chart_lat, item.chart_lon),
                        labelMarker.getLatLng(),
                        item.icon_w,
                        item.icon_h
                    );
                    L.polyline(pts, {
                        color: '{{ this.connector_color }}',
                        weight: 1.5,
                        opacity: {{ this.connector_opacity }}
                    }).addTo(layerGroup);
                });
            }

            updateLines();
            map.on('zoomend moveend', updateLines);
            items.forEach(function(item) {
                var labelMarker = window[item.label_marker_name];
                if (!labelMarker) return;
                labelMarker.on('drag dragend', updateLines);
            });
            window._updateMapConnectors = updateLines;
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, items, chart_radius_px):
        super().__init__()
        self._name = "DynamicConnectors"
        self.map_name = map_name
        self.items = items
        self.chart_radius_px = chart_radius_px
        self.connector_color = CONNECTOR_COLOR
        self.connector_opacity = CONNECTOR_OPACITY


class MapDragGuard(MacroElement):
    """Block label drags and show overlay while Streamlit saves a moved label."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var markerNames = {{ this.marker_names | tojson }};
            var initiallyLocked = {{ this.initially_locked | tojson }};
            window._labelMapInstance = map;

            function forEachLabelMarker(fn) {
                markerNames.forEach(function(name) {
                    var marker = window[name];
                    if (marker) fn(marker);
                });
            }

            function ensureOverlay() {
                var overlay = map._labelMapSyncOverlay;
                if (overlay) return overlay;
                overlay = L.DomUtil.create('div', 'label-map-sync-overlay', map.getContainer());
                overlay.style.cssText = [
                    'position:absolute', 'inset:0', 'z-index:10000',
                    'background:rgba(255,255,255,0.55)', 'display:none',
                    'align-items:center', 'justify-content:center',
                    'pointer-events:all', 'cursor:wait',
                    'font:600 14px/1 system-ui,sans-serif', 'color:#334155'
                ].join(';');
                overlay.innerHTML = (
                    '<div style="padding:8px 14px;background:rgba(255,255,255,0.96);' +
                    'border-radius:6px;box-shadow:0 1px 8px rgba(15,23,42,0.1);">' +
                    {{ this.save_message | tojson }} + '</div>'
                );
                map._labelMapSyncOverlay = overlay;
                return overlay;
            }

            window._lockLabelMapDrags = function() {
                window._labelMapDragLocked = true;
                var overlay = ensureOverlay();
                overlay.style.display = 'flex';
                forEachLabelMarker(function(marker) {
                    if (marker.dragging) marker.dragging.disable();
                });
            };

            window._unlockLabelMapDrags = function() {
                window._labelMapDragLocked = false;
                var overlay = map._labelMapSyncOverlay;
                if (overlay) overlay.style.display = 'none';
                forEachLabelMarker(function(marker) {
                    if (marker.dragging) marker.dragging.enable();
                });
            };

            map.whenReady(function() {
                ensureOverlay();
                if (initiallyLocked) {
                    window._lockLabelMapDrags();
                } else {
                    window._unlockLabelMapDrags();
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        map_name,
        marker_names,
        initially_locked=False,
        save_message=LABEL_SAVE_MESSAGE,
    ):
        super().__init__()
        self._name = "MapDragGuard"
        self.map_name = map_name
        self.marker_names = marker_names
        self.initially_locked = initially_locked
        self.save_message = save_message


class MapSaveComplete(MacroElement):
    """Unlock the map only after a save-cycle render has finished loading."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            map.whenReady(function() {
                if (window._unlockLabelMapDrags) {
                    window._unlockLabelMapDrags();
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name):
        super().__init__()
        self._name = "MapSaveComplete"
        self.map_name = map_name


class LabelDragSync(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        {% for item in this.items %}
        {{ item.marker_name }}.on('dragstart', function(e) {
            if (window._labelMapDragLocked) {
                if (e.target._labelDragOrigin) {
                    e.target.setLatLng(e.target._labelDragOrigin);
                }
                if (e.target.dragging) e.target.dragging.disable();
                return;
            }
            e.target._labelDragOrigin = e.target.getLatLng();
        });
        {{ item.marker_name }}.on('dragend', function(e) {
            if (window._labelMapDragLocked) {
                if (e.target._labelDragOrigin) {
                    e.target.setLatLng(e.target._labelDragOrigin);
                }
                return;
            }
            window._labelMapDragLocked = true;
            if (window._lockLabelMapDrags) {
                window._lockLabelMapDrags();
            }
            var ll = e.target.getLatLng();
            var map = e.target._map;
            var viewPart = '';
            if (map) {
                var center = map.getCenter();
                viewPart = '|' + center.lat + ',' + center.lng + ',' + map.getZoom();
            }
            e.target.setTooltipContent(
                'label:{{ item.idx }}:' + ll.lat + ':' + ll.lng + viewPart
            );
            if (window._updateMapConnectors) {
                window._updateMapConnectors();
            }
            e.target.fire('click');
        });
        {% endfor %}
        {% endmacro %}
        """
    )

    def __init__(self, items):
        super().__init__()
        self._name = "LabelDragSync"
        self.items = items


class MapViewRestore(MacroElement):
    """Apply saved center/zoom without animation after map init (stable label drags)."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            map.whenReady(function() {
                var targetLat = {{ this.center_lat }};
                var targetLon = {{ this.center_lon }};
                var targetZoom = {{ this.zoom }};
                var center = map.getCenter();
                var needsView = (
                    Math.abs(center.lat - targetLat) > 1e-6 ||
                    Math.abs(center.lng - targetLon) > 1e-6 ||
                    map.getZoom() !== targetZoom
                );
                if (needsView) {
                    map.setView(
                        [targetLat, targetLon],
                        targetZoom,
                        {animate: false}
                    );
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, center_lat, center_lon, zoom):
        super().__init__()
        self._name = "MapViewRestore"
        self.map_name = map_name
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom = zoom


class ExportMapStyles(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var style = document.createElement('style');
            style.textContent = `
                html, body {
                    margin: 0;
                    padding: 0;
                    width: {{ this.width }}px;
                    height: {{ this.height }}px;
                    overflow: hidden;
                    background: #fff;
                }
                .folium-map, .leaflet-container {
                    width: {{ this.width }}px !important;
                    height: {{ this.height }}px !important;
                }
                .leaflet-control-container { display: none !important; }
            `;
            document.head.appendChild(style);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, width, height):
        super().__init__()
        self._name = "ExportMapStyles"
        self.width = width
        self.height = height


class ExportReady(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var exportBounds = {{ this.export_bounds | tojson }};
            var exportZoom = {{ this.export_zoom | tojson }};

            function markReady() {
                document.body.setAttribute('data-map-export-ready', 'true');
            }
            function tilesReady() {
                var tiles = document.querySelectorAll('.leaflet-tile');
                if (!tiles.length) return false;
                return Array.from(tiles).every(function(tile) {
                    return tile.complete && tile.naturalWidth > 0;
                });
            }
            function applyView() {
                map.invalidateSize();
                if (exportBounds) {
                    map.fitBounds(
                        L.latLngBounds(
                            L.latLng(exportBounds.south, exportBounds.west),
                            L.latLng(exportBounds.north, exportBounds.east)
                        ),
                        {padding: [0, 0], animate: false, maxZoom: exportZoom || 18}
                    );
                } else if (exportZoom !== null && exportZoom !== undefined) {
                    map.setZoom(exportZoom, {animate: false});
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            }
            function waitForTiles(attempts) {
                if (tilesReady()) {
                    applyView();
                    if (window._updateMapConnectors) window._updateMapConnectors();
                    setTimeout(function() {
                        if (window._updateMapConnectors) window._updateMapConnectors();
                        markReady();
                    }, 500);
                    return;
                }
                if (attempts <= 0) {
                    applyView();
                    markReady();
                    return;
                }
                setTimeout(function() { waitForTiles(attempts - 1); }, 250);
            }
            map.whenReady(function() {
                applyView();
                waitForTiles(50);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, export_bounds=None, export_zoom=None):
        super().__init__()
        self._name = "ExportReady"
        self.map_name = map_name
        self.export_bounds = export_bounds
        self.export_zoom = export_zoom

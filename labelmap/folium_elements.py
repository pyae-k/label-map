"""Custom Folium MacroElements for connectors, drag sync, and export."""

from folium.elements import MacroElement
from jinja2 import Template

from labelmap.config import (
    APP_FONT_STACK,
    APP_TEXT_COLOR,
    DEFAULT_MAP_STYLE,
    LABEL_SAVE_MESSAGE,
    build_legend_style,
    connector_style_for_map_style,
    label_theme_for_map_style,
)


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
                        weight: 2,
                        opacity: {{ this.connector_opacity }},
                        dashArray: null,
                        lineCap: 'round',
                        lineJoin: 'round'
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

    def __init__(self, map_name, items, chart_radius_px, map_style=DEFAULT_MAP_STYLE):
        super().__init__()
        self._name = "DynamicConnectors"
        self.map_name = map_name
        self.items = items
        self.chart_radius_px = chart_radius_px
        connector = connector_style_for_map_style(map_style)
        self.connector_color = connector["color"]
        self.connector_opacity = connector["opacity"]


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
                    'background:rgba(17,17,19,0.55)', 'display:none',
                    'align-items:center', 'justify-content:center',
                    'pointer-events:all', 'cursor:wait',
                    'font-family:' + {{ this.font_stack | tojson }},
                    'font-size:13px',
                    'font-weight:700',
                    'color:{{ this.text_color }}'
                ].join(';');
                overlay.innerHTML = (
                    '<div style="padding:8px 14px;background:rgba(28,28,30,0.96);' +
                    'border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.25);' +
                    'color:{{ this.text_color }};font-family:' +
                    {{ this.font_stack | tojson }} + ';' +
                    'font-weight:700;">' +
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
        self.font_stack = APP_FONT_STACK
        self.text_color = APP_TEXT_COLOR


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
                if (typeof window._labelMapReapplySavedView === 'function') {
                    setTimeout(function() {
                        window._labelMapReapplySavedView();
                    }, 0);
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
            var persistZoom = null;
            if (map) {
                var center = map.getCenter();
                var isFullscreen = false;
                if (typeof map.isFullscreen === 'function') {
                    isFullscreen = map.isFullscreen();
                } else if (map.getContainer) {
                    isFullscreen = map.getContainer().classList.contains(
                        'leaflet-pseudo-fullscreen'
                    );
                }
                var persistZoom = map.getZoom();
                viewPart = (
                    '|' +
                    center.lat +
                    ',' +
                    center.lng +
                    ',' +
                    persistZoom +
                    ',' +
                    (isFullscreen ? '1' : '0')
                );
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


class MapFrameFill(MacroElement):
    """Stretch the Leaflet map to the full Streamlit iframe width and height."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var refW = {{ this.reference_width }};
            var lastStableFrameWidth = 0;

            function isFullscreen() {
                return document.documentElement.classList.contains('labelmap-fs-active');
            }

            function enforceFixedWidth() {
                if (!refW || refW < 1 || isFullscreen()) {
                    return 0;
                }
                try {
                    var parentFrame = window.frameElement;
                    if (parentFrame) {
                        parentFrame.style.width = refW + 'px';
                        parentFrame.style.maxWidth = refW + 'px';
                        parentFrame.style.minWidth = refW + 'px';
                    }
                } catch (e) {}
                document.documentElement.style.width = refW + 'px';
                document.documentElement.style.maxWidth = refW + 'px';
                document.body.style.width = refW + 'px';
                document.body.style.maxWidth = refW + 'px';
                var container = map.getContainer();
                if (container) {
                    container.style.width = refW + 'px';
                    container.style.maxWidth = refW + 'px';
                }
                return refW;
            }

            function frameSize() {
                var frameWidth = 0;
                var frameHeight = 0;
                var fullscreenActive = document.documentElement.classList.contains(
                    'labelmap-fs-active'
                );
                if (fullscreenActive) {
                    frameWidth = window.innerWidth || 0;
                    frameHeight = window.innerHeight || 0;
                    if (frameWidth > 0 && frameHeight > 0) {
                        return {width: frameWidth, height: frameHeight};
                    }
                }
                try {
                    var parentFrame = window.frameElement;
                    if (parentFrame) {
                        frameWidth = parentFrame.clientWidth || 0;
                        frameHeight = parentFrame.clientHeight || 0;
                    }
                } catch (e) {}
                if (frameWidth < 1 || frameHeight < 1) {
                    frameWidth = Math.max(
                        frameWidth,
                        document.documentElement.clientWidth || 0,
                        document.body.clientWidth || 0
                    );
                    frameHeight = Math.max(
                        frameHeight,
                        document.documentElement.clientHeight || 0,
                        document.body.clientHeight || 0
                    );
                }
                return {width: frameWidth, height: frameHeight};
            }

            function fillFrame() {
                var enforcedW = enforceFixedWidth();
                var size = frameSize();
                var frameWidth = enforcedW > 0 ? enforcedW : size.width;
                var frameHeight = size.height;
                if (frameHeight < 50) {
                    return false;
                }
                if (
                    !refW &&
                    window._labelMapViewInitialized &&
                    lastStableFrameWidth > 100 &&
                    Math.abs(frameWidth - lastStableFrameWidth) > 20 &&
                    !window._labelMapFsTransition
                ) {
                    var widthDelta = Math.log(frameWidth / lastStableFrameWidth) / Math.LN2;
                    if (Math.abs(widthDelta) > 0.001) {
                        var resizeCenter = map.getCenter();
                        map.setView(
                            resizeCenter,
                            map.getZoom() + widthDelta,
                            {animate: false}
                        );
                    }
                }
                lastStableFrameWidth = frameWidth;
                map.invalidateSize({animate: false});
                if (typeof window._applySingleWorldMap === 'function') {
                    window._applySingleWorldMap();
                }
                if (
                    window._labelMapViewInitialized &&
                    typeof window._labelMapReapplySavedView === 'function'
                ) {
                    var size = map.getSize();
                    var sizeKey = (size ? size.x : 0) + 'x' + (size ? size.y : 0);
                    if (window._labelMapLastFillSize !== sizeKey) {
                        window._labelMapLastFillSize = sizeKey;
                        window._labelMapReapplySavedView();
                    }
                } else if (typeof window._applyPendingMapView === 'function') {
                    window._applyPendingMapView();
                }
                return true;
            }

            map.whenReady(function() {
                fillFrame();
                window.addEventListener('resize', fillFrame);
            });
            window._fillMapFrame = fillFrame;
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, reference_width=0):
        super().__init__()
        self._name = "MapFrameFill"
        self.map_name = map_name
        self.reference_width = reference_width


class SmoothZoomControl(MacroElement):
    """Fine-grained zoom steps with hold-to-repeat acceleration on +/- buttons."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var baseStep = {{ this.base_step }};
            var maxStep = {{ this.max_step }};
            var holdDelay = {{ this.hold_delay_ms }};
            var repeatMs = {{ this.repeat_ms }};

            function clampZoom(zoom) {
                return Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), zoom));
            }

            function applyZoom(delta) {
                var next = clampZoom(map.getZoom() + delta);
                if (next !== map.getZoom()) {
                    map.setZoom(next);
                    if (typeof window._applySingleWorldMap === 'function') {
                        window._applySingleWorldMap();
                    }
                }
            }

            function stepForHold(elapsedMs) {
                var growth = 1 + elapsedMs / 650;
                return Math.min(maxStep, baseStep * growth);
            }

            function attachHoldZoom(button, direction) {
                if (!button) return;
                L.DomEvent.disableClickPropagation(button);
                L.DomEvent.off(button);

                var holdTimer = null;
                var repeatTimer = null;
                var repeatStart = 0;
                var pressed = false;

                function stop() {
                    pressed = false;
                    if (holdTimer) {
                        clearTimeout(holdTimer);
                        holdTimer = null;
                    }
                    if (repeatTimer) {
                        clearInterval(repeatTimer);
                        repeatTimer = null;
                    }
                }

                function isDisabled() {
                    return L.DomUtil.hasClass(button, 'leaflet-disabled');
                }

                function startRepeat() {
                    repeatStart = Date.now();
                    repeatTimer = setInterval(function() {
                        if (isDisabled()) {
                            stop();
                            return;
                        }
                        var elapsed = Date.now() - repeatStart;
                        applyZoom(direction * stepForHold(elapsed));
                    }, repeatMs);
                }

                function onPress(e) {
                    if (isDisabled() || pressed) return;
                    pressed = true;
                    L.DomEvent.preventDefault(e);
                    L.DomEvent.stopPropagation(e);
                    applyZoom(direction * baseStep);
                    stop();
                    holdTimer = setTimeout(startRepeat, holdDelay);
                }

                L.DomEvent.on(button, 'mousedown', onPress);
                L.DomEvent.on(button, 'touchstart', onPress);
                L.DomEvent.on(button, 'mouseup', stop);
                L.DomEvent.on(button, 'mouseleave', stop);
                L.DomEvent.on(button, 'touchend', stop);
                L.DomEvent.on(button, 'touchcancel', stop);
                L.DomEvent.on(button, 'click', function(e) {
                    L.DomEvent.preventDefault(e);
                    L.DomEvent.stopPropagation(e);
                });
            }

            map.whenReady(function() {
                map.options.zoomDelta = baseStep;
                var root = map.getContainer();
                attachHoldZoom(root.querySelector('.leaflet-control-zoom-in'), 1);
                attachHoldZoom(root.querySelector('.leaflet-control-zoom-out'), -1);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        map_name,
        base_step,
        max_step,
        hold_delay_ms,
        repeat_ms,
    ):
        super().__init__()
        self._name = "SmoothZoomControl"
        self.map_name = map_name
        self.base_step = base_step
        self.max_step = max_step
        self.hold_delay_ms = hold_delay_ms
        self.repeat_ms = repeat_ms


class SingleWorldMap(MacroElement):
    """Keep one world copy: no horizontal tile repeat, bounded panning."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var worldBounds = L.latLngBounds(
                L.latLng(-85.05112878, -180),
                L.latLng(85.05112878, 180)
            );

            function minZoomForContainer() {
                var size = map.getSize();
                var width = size && size.x ? size.x : 0;
                if (width < 1) {
                    var refW = {{ this.reference_width }};
                    if (refW > 0) {
                        width = refW;
                    }
                }
                if (width < 1) {
                    return {{ this.fallback_min_zoom }};
                }
                return Math.max(0, Math.log(width / 256) / Math.LN2);
            }

            function snapWorldCenterAtMinZoom(minZoom) {
                if (map.getZoom() > minZoom + 0.05) {
                    return;
                }
                var center = map.getCenter();
                if (Math.abs(center.lng) < 0.05) {
                    return;
                }
                map.setView(
                    [center.lat, 0],
                    Math.max(minZoom, map.getZoom()),
                    {animate: false}
                );
            }

            function applySingleWorld() {
                map.setMaxBounds(worldBounds);
                map.options.maxBoundsViscosity = 1.0;
                map.eachLayer(function(layer) {
                    if (typeof layer.setNoWrap === 'function') {
                        layer.setNoWrap(true);
                    } else if (layer.options) {
                        layer.options.noWrap = true;
                    }
                });
                var minZoom = minZoomForContainer();
                if (map.getMinZoom() !== minZoom) {
                    map.setMinZoom(minZoom);
                }
                if (map.getZoom() < minZoom) {
                    var center = map.getCenter();
                    map.setView([center.lat, 0], minZoom, {animate: false});
                } else {
                    snapWorldCenterAtMinZoom(minZoom);
                }
                map.invalidateSize({animate: false});
            }

            map.whenReady(function() {
                applySingleWorld();
                map.on('resize', applySingleWorld);
                map.on('zoomend', applySingleWorld);
                map.on('moveend', function() {
                    snapWorldCenterAtMinZoom(minZoomForContainer());
                });
            });
            window._applySingleWorldMap = applySingleWorld;
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, fallback_min_zoom, reference_width):
        super().__init__()
        self._name = "SingleWorldMap"
        self.map_name = map_name
        self.fallback_min_zoom = fallback_min_zoom
        self.reference_width = reference_width


class MapViewRestore(MacroElement):
    """Apply saved center/zoom without animation after map init (stable label drags)."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var targetLat = {{ this.center_lat }};
            var targetLon = {{ this.center_lon }};
            var targetZoom = {{ this.zoom }};
            var targetFullscreen = {{ this.fullscreen | tojson }};
            var worldFit = {{ this.world_fit | tojson }};
            var minMapHeight = 50;
            var initialViewApplied = false;
            var worldBounds = L.latLngBounds(
                L.latLng(-85.05112878, -180),
                L.latLng(85.05112878, 180)
            );

            function mapIsFullscreen() {
                if (typeof map.isFullscreen === 'function') {
                    return map.isFullscreen();
                }
                return map.getContainer().classList.contains('leaflet-pseudo-fullscreen');
            }

            function zoomMatches(currentZoom, desiredZoom) {
                return Math.abs(currentZoom - desiredZoom) <= 0.02;
            }

            function centerMatches(center) {
                var latTol = Math.abs(targetZoom) <= 0.05 ? 5.0 : 0.5;
                var lonTol = latTol;
                return (
                    Math.abs(center.lat - targetLat) <= latTol &&
                    Math.abs(center.lng - targetLon) <= lonTol
                );
            }

            function mapHasValidSize() {
                var size = map.getSize();
                return Boolean(size && size.x > 0 && size.y >= minMapHeight);
            }

            function containerRelativeZoom(savedZoom) {
                var minZoom = map.getMinZoom();
                var refDefaultZoom = {{ this.reference_default_zoom }};
                var fitZoom = map.getBoundsZoom(worldBounds, false);
                var zoomOffset = savedZoom - refDefaultZoom;
                if (Math.abs(zoomOffset) <= 0.02) {
                    return minZoom;
                }
                // Sessions saved before logical-offset zoom stored absolute Leaflet zoom.
                if (savedZoom >= fitZoom - 0.02 && zoomOffset > 0.5) {
                    return Math.max(minZoom, savedZoom);
                }
                return Math.max(minZoom, fitZoom + zoomOffset);
            }

            function applyWorldDefaultView() {
                if (typeof window._applySingleWorldMap === 'function') {
                    window._applySingleWorldMap();
                }
                map.invalidateSize({animate: false});
                var minZoom = map.getMinZoom();
                var offset = {{ this.default_zoom_offset }};
                var fitTargetZoom = offset > 0
                    ? Math.max(minZoom, map.getBoundsZoom(worldBounds, false) + offset)
                    : minZoom;
                map.setView([0, 0], fitTargetZoom, {animate: false});
                map.eachLayer(function(layer) {
                    if (layer.redraw) {
                        layer.redraw();
                    }
                });
            }

            function applySavedView(zoomOnly) {
                var center = map.getCenter();
                var adjustedZoom = containerRelativeZoom(targetZoom);
                var zoomOk = zoomMatches(map.getZoom(), adjustedZoom);
                if (zoomOnly) {
                    if (zoomOk) {
                        return;
                    }
                    map.setZoom(adjustedZoom, {animate: false});
                    return;
                }
                var needsView = !centerMatches(center) || !zoomOk;
                if (!needsView) {
                    return;
                }
                var viewKey = (
                    targetLat.toFixed(5) + ',' +
                    targetLon.toFixed(5) + ',' +
                    adjustedZoom.toFixed(3)
                );
                if (window._labelMapLastAppliedViewKey === viewKey) {
                    return;
                }
                window._labelMapLastAppliedViewKey = viewKey;
                map.setView(
                    [targetLat, targetLon],
                    adjustedZoom,
                    {animate: false}
                );
            }

            function applyRestoredFullscreenZoom() {
                var fsZoomDelta = map._labelMapFsZoomDelta || 0;
                if (!targetFullscreen || !fsZoomDelta || map._labelMapFsZoomActive) {
                    return;
                }
                if (!mapIsFullscreen()) {
                    return;
                }
                var next = Math.max(
                    map.getMinZoom(),
                    Math.min(map.getMaxZoom(), map.getZoom() + fsZoomDelta)
                );
                if (next !== map.getZoom()) {
                    map.setZoom(next, {animate: false});
                }
                map._labelMapFsZoomActive = true;
            }

            function syncFullscreen() {
                if (
                    typeof map.restoreFullscreen !== 'function' &&
                    typeof map.toggleFullscreen !== 'function'
                ) {
                    return;
                }
                var isFullscreen = mapIsFullscreen();
                if (targetFullscreen && !isFullscreen) {
                    window._labelMapRestoringFs = true;
                    if (typeof map.restoreFullscreen === 'function') {
                        map.restoreFullscreen();
                    } else if (typeof map.toggleFullscreen === 'function') {
                        map.toggleFullscreen();
                    }
                    setTimeout(function() {
                        applyRestoredFullscreenZoom();
                        window._labelMapRestoringFs = false;
                    }, 250);
                } else if (!targetFullscreen && isFullscreen) {
                    map._labelMapFsZoomActive = false;
                    if (typeof map.toggleFullscreen === 'function') {
                        map.toggleFullscreen(false);
                    }
                }
            }

            function applyLayoutRefresh() {
                map.invalidateSize({animate: false});
                if (typeof window._applySingleWorldMap === 'function') {
                    window._applySingleWorldMap();
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            }

            function finalizeViewRestore() {
                if (window._labelMapDragLocked) {
                    if (window._updateMapConnectors) {
                        window._updateMapConnectors();
                    }
                    return;
                }
                applyLayoutRefresh();
            }

            function applyPendingMapView() {
                if (!mapHasValidSize()) {
                    return false;
                }
                if (!initialViewApplied) {
                    if (worldFit) {
                        applyWorldDefaultView();
                    } else {
                        applySavedView(false);
                    }
                    syncFullscreen();
                    initialViewApplied = true;
                    window._labelMapViewInitialized = true;
                }
                finalizeViewRestore();
                return true;
            }

            window._applyPendingMapView = applyPendingMapView;
            window._labelMapReapplySavedView = function() {
                if (!mapHasValidSize()) {
                    return false;
                }
                applySavedView(true);
                finalizeViewRestore();
                return true;
            };
            if (worldFit) {
                window._applyWorldDefaultView = applyWorldDefaultView;
            }

            function tryRestoreView(attempts) {
                if (typeof window._fillMapFrame === 'function') {
                    window._fillMapFrame();
                }
                if (applyPendingMapView()) {
                    return;
                }
                if (attempts <= 0) {
                    return;
                }
                setTimeout(function() {
                    tryRestoreView(attempts - 1);
                }, 50);
            }

            map.whenReady(function() {
                tryRestoreView(20);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        map_name,
        center_lat,
        center_lon,
        zoom,
        fullscreen=False,
        world_fit=False,
        default_zoom_offset=0.0,
        reference_default_zoom=0.0,
    ):
        super().__init__()
        self._name = "MapViewRestore"
        self.map_name = map_name
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom = zoom
        self.fullscreen = fullscreen
        self.world_fit = world_fit
        self.default_zoom_offset = default_zoom_offset
        self.reference_default_zoom = reference_default_zoom


class MapFullscreenControl(MacroElement):
    """Fullscreen toggle inside the zoom pill; works inside Streamlit iframes."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var titleEnter = {{ this.title | tojson }};
            var titleExit = {{ this.title_cancel | tojson }};
            var zoomStep = {{ this.zoom_step }};
            var zoomClicks = {{ this.zoom_clicks }};
            var fsZoomDelta = zoomStep * zoomClicks;
            map._labelMapFsZoomDelta = fsZoomDelta;
            var worldBounds = L.latLngBounds(
                L.latLng(-85.05112878, -180),
                L.latLng(85.05112878, 180)
            );

            function containerFitZoom() {
                return map.getBoundsZoom(worldBounds, false);
            }

            map.getPersistedZoom = function() {
                var zoom = map.getZoom();
                if (map._labelMapFsZoomActive && fsZoomDelta) {
                    zoom -= fsZoomDelta;
                }
                return Math.max(0, zoom - containerFitZoom());
            };
            var frameExpandStyle =
                'position:fixed!important;top:0!important;left:0!important;' +
                'right:0!important;bottom:0!important;width:100vw!important;' +
                'height:100vh!important;max-width:none!important;max-height:none!important;' +
                'z-index:999999!important;border:none!important;margin:0!important;';

            function beginFsTransition() {
                window._labelMapFsTransition = true;
                clearTimeout(window._labelMapFsTransitionTimer);
                window._labelMapFsTransitionTimer = setTimeout(function() {
                    window._labelMapFsTransition = false;
                }, 400);
            }

            function getFrameEl() {
                try {
                    return window.frameElement || null;
                } catch (e) {
                    return null;
                }
            }

            function parentFullscreenElement() {
                try {
                    if (!window.parent || !window.parent.document) return null;
                    var parentDoc = window.parent.document;
                    return (
                        parentDoc.fullscreenElement ||
                        parentDoc.webkitFullscreenElement ||
                        parentDoc.mozFullScreenElement ||
                        parentDoc.msFullscreenElement ||
                        null
                    );
                } catch (e) {
                    return null;
                }
            }

            function activeFullscreenElement() {
                return (
                    document.fullscreenElement ||
                    document.webkitFullscreenElement ||
                    document.mozFullScreenElement ||
                    document.msFullscreenElement ||
                    null
                );
            }

            function isNativeFullscreen() {
                var frame = getFrameEl();
                if (frame && parentFullscreenElement() === frame) {
                    return true;
                }
                var active = activeFullscreenElement();
                return Boolean(frame && active === frame) || Boolean(active);
            }

            function mapIsFullscreen() {
                if (isNativeFullscreen()) {
                    return true;
                }
                return (
                    document.documentElement.classList.contains('labelmap-fs-active') ||
                    map.getContainer().classList.contains('leaflet-pseudo-fullscreen')
                );
            }

            function setFullscreenButtonState(link, on) {
                if (!link) return;
                if (on) {
                    L.DomUtil.addClass(link, 'leaflet-fullscreen-on');
                    link.title = titleExit;
                    link.setAttribute('aria-label', titleExit);
                } else {
                    L.DomUtil.removeClass(link, 'leaflet-fullscreen-on');
                    link.title = titleEnter;
                    link.setAttribute('aria-label', titleEnter);
                }
            }

            function applyFullscreenZoom(delta) {
                if (window._labelMapRestoringFs || !fsZoomDelta) {
                    return;
                }
                var next = Math.max(
                    map.getMinZoom(),
                    Math.min(map.getMaxZoom(), map.getZoom() + delta)
                );
                if (next !== map.getZoom()) {
                    map.setZoom(next, {animate: false});
                }
            }

            function afterResize() {
                map.invalidateSize({animate: false});
                if (typeof window._fillMapFrame === 'function') {
                    window._fillMapFrame();
                }
                if (typeof window._applySingleWorldMap === 'function') {
                    window._applySingleWorldMap();
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            }

            function applyFullscreenSizing() {
                document.documentElement.classList.add('labelmap-fs-active');
                document.body.classList.add('labelmap-fs-active');
                var mapDiv = document.getElementById('map_div');
                if (mapDiv) {
                    mapDiv.classList.add('labelmap-fs-active');
                }
            }

            function removeFullscreenSizing() {
                document.documentElement.classList.remove('labelmap-fs-active');
                document.body.classList.remove('labelmap-fs-active');
                var mapDiv = document.getElementById('map_div');
                if (mapDiv) {
                    mapDiv.classList.remove('labelmap-fs-active');
                }
            }

            function markFrameExpanded(frame) {
                if (!frame || frame._labelMapExpanded) {
                    return;
                }
                frame._labelMapExpanded = true;
                frame._labelMapOrigStyle = frame.getAttribute('style');
                frame.style.cssText = (frame._labelMapOrigStyle || '') + ';' + frameExpandStyle;
            }

            function expandEmbedFrames() {
                applyFullscreenSizing();
                try {
                    var win = window;
                    while (win && win !== win.parent) {
                        var frame = win.frameElement;
                        if (frame) {
                            markFrameExpanded(frame);
                        }
                        win = win.parent;
                    }
                } catch (e) {}
            }

            function collapseEmbedFrames() {
                try {
                    var win = window;
                    while (win && win !== win.parent) {
                        var frame = win.frameElement;
                        if (frame && frame._labelMapExpanded) {
                            frame._labelMapExpanded = false;
                            if (
                                frame._labelMapOrigStyle === null ||
                                frame._labelMapOrigStyle === undefined
                            ) {
                                frame.removeAttribute('style');
                            } else {
                                frame.setAttribute('style', frame._labelMapOrigStyle);
                            }
                            delete frame._labelMapOrigStyle;
                        }
                        win = win.parent;
                    }
                } catch (e) {}
            }

            function enterPseudoFullscreen() {
                L.DomUtil.addClass(map.getContainer(), 'leaflet-pseudo-fullscreen');
                afterResize();
            }

            function exitPseudoFullscreen() {
                L.DomUtil.removeClass(map.getContainer(), 'leaflet-pseudo-fullscreen');
                afterResize();
            }

            function requestElementFullscreen(el) {
                if (!el) {
                    return Promise.reject(new Error('no element'));
                }
                var req =
                    el.requestFullscreen ||
                    el.webkitRequestFullscreen ||
                    el.mozRequestFullScreen ||
                    el.msRequestFullscreen;
                if (!req) {
                    return Promise.reject(new Error('no fullscreen api'));
                }
                try {
                    var result = req.call(el);
                    return result && result.then ? result : Promise.resolve();
                } catch (err) {
                    return Promise.reject(err);
                }
            }

            function finishEnterFullscreen() {
                var link = map._controlContainer.querySelector(
                    '.leaflet-control-zoom-fullscreen'
                );
                setFullscreenButtonState(link, true);
                afterResize();
                setTimeout(afterResize, 50);
                setTimeout(function() {
                    afterResize();
                    if (!window._labelMapRestoringFs) {
                        applyFullscreenZoom(fsZoomDelta);
                        map._labelMapFsZoomActive = true;
                    }
                }, 200);
                map.fire('enterFullscreen');
                map.fire('fullscreenchange');
            }

            function enterExpandedFullscreen() {
                expandEmbedFrames();
                enterPseudoFullscreen();
                finishEnterFullscreen();
            }

            function enterFullscreen() {
                beginFsTransition();
                var frame = getFrameEl();
                if (frame) {
                    requestElementFullscreen(frame)
                        .then(function() {
                            applyFullscreenSizing();
                            finishEnterFullscreen();
                        })
                        .catch(function() {
                            enterExpandedFullscreen();
                        });
                    return;
                }
                enterExpandedFullscreen();
            }

            function exitFullscreen(adjustZoom) {
                beginFsTransition();
                try {
                    if (window.parent && window.parent.document && parentFullscreenElement()) {
                        var parentDoc = window.parent.document;
                        var parentExit =
                            parentDoc.exitFullscreen ||
                            parentDoc.webkitExitFullscreen ||
                            parentDoc.mozCancelFullScreen ||
                            parentDoc.msExitFullscreen;
                        if (parentExit) {
                            parentExit.call(parentDoc);
                        }
                    }
                } catch (e) {}
                var active = activeFullscreenElement();
                if (active) {
                    var localExit =
                        document.exitFullscreen ||
                        document.webkitExitFullscreen ||
                        document.mozCancelFullScreen ||
                        document.msExitFullscreen;
                    if (localExit) {
                        localExit.call(document);
                    }
                }
                removeFullscreenSizing();
                collapseEmbedFrames();
                exitPseudoFullscreen();
                if (adjustZoom !== false && map._labelMapFsZoomActive) {
                    applyFullscreenZoom(-fsZoomDelta);
                    map._labelMapFsZoomActive = false;
                }
            }

            function toggleFullscreen(adjustZoomOnExit) {
                if (mapIsFullscreen()) {
                    exitFullscreen(adjustZoomOnExit);
                    var link = map._controlContainer.querySelector(
                        '.leaflet-control-zoom-fullscreen'
                    );
                    setFullscreenButtonState(link, false);
                    map.fire('exitFullscreen');
                    map.fire('fullscreenchange');
                } else {
                    enterFullscreen();
                }
            }

            map.isFullscreen = mapIsFullscreen;
            map.toggleFullscreen = toggleFullscreen;
            map.restoreFullscreen = enterExpandedFullscreen;

            function integrateControl() {
                var zoomCtrl = map._controlContainer.querySelector('.leaflet-control-zoom');
                if (!zoomCtrl) return null;

                var link = zoomCtrl.querySelector('.leaflet-control-zoom-fullscreen');
                if (!link) {
                    link = L.DomUtil.create(
                        'a',
                        'leaflet-control-zoom-fullscreen fullscreen-icon',
                        zoomCtrl
                    );
                    link.href = '#';
                    link.setAttribute('role', 'button');
                    L.DomEvent.on(link, 'click', L.DomEvent.stopPropagation);
                    L.DomEvent.on(link, 'click', L.DomEvent.preventDefault);
                    L.DomEvent.on(link, 'click', toggleFullscreen);
                }
                setFullscreenButtonState(link, mapIsFullscreen());
                return link;
            }

            function onNativeFullscreenChange() {
                var nativeFs = isNativeFullscreen();
                var pseudoClass = map.getContainer().classList.contains('leaflet-pseudo-fullscreen');
                var fsActive = document.documentElement.classList.contains('labelmap-fs-active');
                if (nativeFs) {
                    applyFullscreenSizing();
                    afterResize();
                } else if (!pseudoClass && !fsActive) {
                    removeFullscreenSizing();
                    collapseEmbedFrames();
                    exitPseudoFullscreen();
                }
                var link = map._controlContainer.querySelector(
                    '.leaflet-control-zoom-fullscreen'
                );
                var on = mapIsFullscreen();
                setFullscreenButtonState(link, on);
                afterResize();
                if (!on && map._labelMapFsZoomActive && !window._labelMapRestoringFs) {
                    setTimeout(function() {
                        afterResize();
                        applyFullscreenZoom(-fsZoomDelta);
                        map._labelMapFsZoomActive = false;
                    }, 200);
                }
                map.fire(on ? 'enterFullscreen' : 'exitFullscreen');
                map.fire('fullscreenchange');
            }

            function onMapResize() {
                if (mapIsFullscreen()) {
                    afterResize();
                }
            }

            function bindFullscreenListeners(target) {
                if (!target || target._labelMapFullscreenBound) return;
                target._labelMapFullscreenBound = true;
                target.addEventListener('fullscreenchange', onNativeFullscreenChange);
                target.addEventListener('webkitfullscreenchange', onNativeFullscreenChange);
                target.addEventListener('mozfullscreenchange', onNativeFullscreenChange);
                target.addEventListener('MSFullscreenChange', onNativeFullscreenChange);
            }

            map.whenReady(function() {
                integrateControl();
                bindFullscreenListeners(document);
                try {
                    if (window.parent && window.parent.document) {
                        bindFullscreenListeners(window.parent.document);
                    }
                } catch (e) {}
                window.addEventListener('resize', onMapResize);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        map_name,
        title="Full screen",
        title_cancel="Exit full screen",
        zoom_step=0.12,
        zoom_clicks=4,
    ):
        super().__init__()
        self._name = "MapFullscreenControl"
        self.map_name = map_name
        self.title = title
        self.title_cancel = title_cancel
        self.zoom_step = zoom_step
        self.zoom_clicks = zoom_clicks


class FullscreenStateSync(MacroElement):
    """Persist map view (center, zoom, fullscreen) to Streamlit."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var syncMarker = {{ this.sync_marker_name }};
            var syncing = false;

            function mapIsFullscreen() {
                if (typeof map.isFullscreen === 'function') {
                    return map.isFullscreen();
                }
                return map.getContainer().classList.contains('leaflet-pseudo-fullscreen');
            }

            function currentMarkerTooltip() {
                if (!syncMarker || !syncMarker.getTooltip) {
                    return '';
                }
                var tip = syncMarker.getTooltip();
                if (!tip || !tip.getContent) {
                    return '';
                }
                var content = tip.getContent();
                return typeof content === 'string' ? content : '';
            }

            function publishViewState() {
                if (!syncMarker || syncing || window._labelMapDragLocked) {
                    return;
                }
                if (window._labelMapRestoringFs) {
                    return;
                }
                syncing = true;
                var center = map.getCenter();
                var fsFlag = mapIsFullscreen() ? '1' : '0';
                var persistZoom = map.getZoom();
                var newTooltip =
                    'view:fs:' + fsFlag + '|' +
                    center.lat + ',' + center.lng + ',' + persistZoom;
                if (currentMarkerTooltip() === newTooltip) {
                    syncing = false;
                    return;
                }
                syncMarker.setTooltipContent(newTooltip);
                map.invalidateSize({animate: false});
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
                syncMarker.fire('click');
                setTimeout(function() { syncing = false; }, 300);
            }

            map.whenReady(function() {
                map.on(
                    'enterFullscreen exitFullscreen fullscreenchange',
                    publishViewState
                );
                document.addEventListener('fullscreenchange', publishViewState);
                document.addEventListener('webkitfullscreenchange', publishViewState);
                try {
                    if (window.parent && window.parent.document) {
                        window.parent.document.addEventListener(
                            'fullscreenchange',
                            publishViewState
                        );
                        window.parent.document.addEventListener(
                            'webkitfullscreenchange',
                            publishViewState
                        );
                    }
                } catch (e) {}
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, sync_marker_name):
        super().__init__()
        self._name = "FullscreenStateSync"
        self.map_name = map_name
        self.sync_marker_name = sync_marker_name


class MapLegend(MacroElement):
    """Bottom-left legend matching label panel transparency."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var items = {{ this.items | tojson }};
            if (!items.length) return;

            var LegendControl = L.Control.extend({
                options: { position: 'bottomleft' },
                onAdd: function() {
                    var container = L.DomUtil.create('div', 'label-map-legend');
                    container.style.cssText = {{ this.legend_style | tojson }};
                    container.style.marginBottom = '28px';
                    container.style.pointerEvents = 'none';
                    var rows = items.map(function(item) {
                        var hasSwatch = Boolean(item.color);
                        var gap = hasSwatch ? '4' : '0';
                        var marginTop = item.spacer_before ? '8px' : '2px';
                        var labelStyle = 'color:{{ this.muted_color }};' +
                            (item.muted ? 'opacity:0.92;' : '');
                        var swatch = hasSwatch ? (
                            '<span style="display:inline-block;width:9px;height:9px;' +
                            'border-radius:2px;background:' + item.color +
                            ';border:1px solid {{ this.swatch_border }};' +
                            'flex:0 0 auto;"></span>'
                        ) : '';
                        return (
                            '<div style="display:flex;align-items:center;gap:' + gap +
                            'px;margin:' + marginTop + ' 0 2px;">' +
                            swatch +
                            '<span style="' + labelStyle + '">' + item.label + '</span>' +
                            '</div>'
                        );
                    }).join('');
                    container.innerHTML = rows;
                    return container;
                }
            });
            var map = {{ this.map_name }};
            map.whenReady(function() {
                new LegendControl().addTo(map);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, items, map_style=DEFAULT_MAP_STYLE):
        super().__init__()
        self._name = "MapLegend"
        self.map_name = map_name
        self.items = items
        theme = label_theme_for_map_style(map_style)
        self.legend_style = build_legend_style(map_style)
        self.muted_color = theme["muted_color"]
        self.swatch_border = theme["swatch_border"]


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
                .leaflet-control-zoom,
                .leaflet-control-fullscreen,
                .leaflet-control-attribution {
                    display: none !important;
                }
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

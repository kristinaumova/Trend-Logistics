import { useEffect, useRef } from 'react'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import { fromLonLat } from 'ol/proj'
import { LineString, Point } from 'ol/geom'
import Feature from 'ol/Feature'
import Style from 'ol/style/Style'
import Stroke from 'ol/style/Stroke'
import CircleStyle from 'ol/style/Circle'
import Fill from 'ol/style/Fill'
import 'ol/ol.css'

// CartoDB Voyager — цветная подложка: земля, вода, дороги, подписи
const TILE_URL = 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'

const ROUTE_COLOR = '#059669'                       // насыщенный зелёный
const ROUTE_GLOW = 'rgba(5, 150, 105, 0.35)'      // свечение маршрута
const ORIGIN_FILL = '#10b981'                       // старт
const ORIGIN_STROKE = '#047857'
const DEST_FILL = '#2563eb'                         // финиш
const DEST_STROKE = '#1d4ed8'
const CARGO_FILL = '#f59e0b'                        // эмуляция GPS
const CARGO_STROKE = '#b45309'

/** [lat, lon] → [lon, lat] для OpenLayers */
function toLonLat(point) {
  if (!point || point.length < 2) return null
  return [point[1], point[0]]
}

/** cargoPosition: { lat, lon } — текущая позиция груза (телеметрия) */
export default function RouteMap({ origin, destination, coordinates, cargoPosition, className }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const vectorSourceRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    const hasRoute = Array.isArray(coordinates) && coordinates.length > 1
    const hasCargo = cargoPosition?.lat != null && cargoPosition?.lon != null
    const hasPoints = (origin && destination) || hasRoute || hasCargo
    if (!hasPoints) return

    if (!mapRef.current) {
      const vectorSource = new VectorSource()
      vectorSourceRef.current = vectorSource

      const routeLayer = new VectorLayer({
        source: vectorSource,
        style: (feature) => {
          const geom = feature.getGeometry()
          const isOrigin = feature.get('isOrigin')
          const isDest = feature.get('isDest')
          const isCargo = feature.get('isCargo')

          if (geom instanceof LineString) {
            return [
              new Style({
                stroke: new Stroke({
                  color: ROUTE_GLOW,
                  width: 14,
                  lineCap: 'round',
                  lineJoin: 'round',
                }),
              }),
              new Style({
                stroke: new Stroke({
                  color: ROUTE_COLOR,
                  width: 5,
                  lineCap: 'round',
                  lineJoin: 'round',
                }),
              }),
            ]
          }

          if (isCargo) {
            return [
              new Style({
                image: new CircleStyle({
                  radius: 14,
                  fill: new Fill({ color: 'rgba(245, 158, 11, 0.25)' }),
                  stroke: null,
                }),
              }),
              new Style({
                image: new CircleStyle({
                  radius: 10,
                  fill: new Fill({ color: CARGO_FILL }),
                  stroke: new Stroke({ color: CARGO_STROKE, width: 3 }),
                }),
              }),
            ]
          }

          const isDestPoint = !!isDest
          const fill = isDestPoint ? DEST_FILL : ORIGIN_FILL
          const stroke = isDestPoint ? DEST_STROKE : ORIGIN_STROKE
          return [
            new Style({
              image: new CircleStyle({
                radius: 12,
                fill: new Fill({ color: 'rgba(0,0,0,0.12)' }),
                stroke: null,
              }),
            }),
            new Style({
              image: new CircleStyle({
                radius: 9,
                fill: new Fill({ color: fill }),
                stroke: new Stroke({ color: stroke, width: 3 }),
              }),
            }),
          ]
        },
      })

      const map = new Map({
        target: containerRef.current,
        layers: [
          new TileLayer({
            source: new XYZ({ url: TILE_URL }),
          }),
          routeLayer,
        ],
        view: new View({
          center: fromLonLat([37.6, 55.75]),
          zoom: 4,
        }),
      })
      mapRef.current = map
    }

    const vectorSource = vectorSourceRef.current
    vectorSource.clear()

    const originLonLat = toLonLat(origin)
    const destLonLat = toLonLat(destination)

    if (originLonLat) {
      const f = new Feature(new Point(fromLonLat(originLonLat)))
      f.set('isOrigin', true)
      vectorSource.addFeature(f)
    }
    if (destLonLat) {
      const f = new Feature(new Point(fromLonLat(destLonLat)))
      f.set('isDest', true)
      vectorSource.addFeature(f)
    }

    if (hasCargo) {
      const cargoLonLat = [cargoPosition.lon, cargoPosition.lat]
      const f = new Feature(new Point(fromLonLat(cargoLonLat)))
      f.set('isCargo', true)
      vectorSource.addFeature(f)
    }

    if (hasRoute && coordinates.length > 1) {
      const lineCoords = coordinates.map((c) => fromLonLat(toLonLat(c)))
      vectorSource.addFeature(new Feature(new LineString(lineCoords)))
      const extent = new LineString(lineCoords).getExtent()
      mapRef.current.getView().fit(extent, {
        padding: [40, 40, 40, 40],
        maxZoom: 11,
        duration: 400,
      })
    } else if (originLonLat && destLonLat) {
      mapRef.current.getView().fit(
        new LineString([fromLonLat(originLonLat), fromLonLat(destLonLat)]).getExtent(),
        { padding: [60, 60, 60, 60], maxZoom: 11, duration: 400 }
      )
    }
  }, [origin, destination, coordinates, cargoPosition])

  return (
    <div className={`route-map-container ${className || ''}`}>
      <div ref={containerRef} className="route-map-inner" />
      <div className="route-map-legend">
        <span className="route-map-legend-dot origin" /> Отправление
        <span className="route-map-legend-dot dest" /> Назначение
        {cargoPosition && (
          <>
            <span className="route-map-legend-dot cargo" /> Груз
          </>
        )}
      </div>
    </div>
  )
}

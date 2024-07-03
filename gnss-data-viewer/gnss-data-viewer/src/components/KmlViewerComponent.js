import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import omnivore from 'leaflet-omnivore';

const KmlViewerComponent = ({ kmlFile }) => {
  const mapRef = useRef(null);
  const kmlLayerRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current) {
      mapRef.current = L.map('map').setView([51.505, -0.09], 2);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(mapRef.current);
    }

    if (kmlFile) {
      if (kmlLayerRef.current) {
        mapRef.current.removeLayer(kmlLayerRef.current);
      }

      kmlLayerRef.current = omnivore.kml(kmlFile, null, L.geoJson(null, {
        pointToLayer: (feature, latlng) => {
          return L.marker(latlng, {
            icon: L.icon({
              iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
              iconSize: [25, 41],
              iconAnchor: [12, 41],
              popupAnchor: [1, -34],
              shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
              shadowSize: [41, 41]
            })
          }).bindPopup(feature.properties.name || "No name");
        }
      }));
      kmlLayerRef.current.addTo(mapRef.current);

      kmlLayerRef.current.on('ready', () => {
        mapRef.current.fitBounds(kmlLayerRef.current.getBounds());
      });

      return () => {
        if (kmlLayerRef.current) {
          mapRef.current.removeLayer(kmlLayerRef.current);
        }
      };
    }
  }, [kmlFile]);

  return <div id="map" style={{ height: '100vh', width: '100%' }} />;
};

export default KmlViewerComponent;

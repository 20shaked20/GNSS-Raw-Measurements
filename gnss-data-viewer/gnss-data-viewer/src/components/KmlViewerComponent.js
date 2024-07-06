// src/components/KmlViewerComponent.js
import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import omnivore from 'leaflet-omnivore';
import axios from 'axios';

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

    const fetchKmlData = async () => {
      try {
        const response = await axios.get('http://localhost:5000/live-kml', {
          responseType: 'blob',
        });
        const kmlBlob = new Blob([response.data], { type: 'application/vnd.google-earth.kml+xml' });
        const kmlUrl = URL.createObjectURL(kmlBlob);

        if (kmlLayerRef.current) {
          mapRef.current.removeLayer(kmlLayerRef.current);
        }

        kmlLayerRef.current = omnivore.kml(kmlUrl, null, L.geoJson(null, {
          pointToLayer: (feature, latlng) => {
            let iconUrl = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png';
            if (feature.properties.styleUrl === '#26') {
              iconUrl = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png';
            } else if (feature.properties.styleUrl === '#29') {
              iconUrl = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png';
            }

            return L.marker(latlng, {
              icon: L.icon({
                iconUrl: iconUrl,
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

      } catch (error) {
        console.error('Error fetching KML data:', error);
      }
    };

    const interval = setInterval(fetchKmlData, 5000); // Fetch KML data every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return <div id="map" style={{ height: '100vh', width: '100%' }} />;
};

export default KmlViewerComponent;

# Example data sources

Open data used by the gallery. The files are frozen here so the
documentation build is reproducible and offline.

## cardio_mortalite_dep.csv
- Indicator: mortality from heart failure, standardised rate per
  100,000 inhabitants, 2020-2022 average, by department.
- Source: Sante publique France, ODISSE platform,
  dataset "Maladies cardio-neuro-vasculaires : taux standardises (Departement)".
- Licence: Licence Ouverte / Open Licence (Etalab).

## canicule_exces_75_2025.csv
- Indicator: excess deaths during heatwaves, year 2025, age group
  "over 75", by department.
- Source: Sante publique France, ODISSE platform,
  dataset "Canicules : exces de deces pendant les vagues de chaleur (Departement)".
- Licence: Licence Ouverte / Open Licence (Etalab).

## paris_africa_air_traffic.csv
- Indicator: air passengers carried in 2024 between the Paris airports
  (Charles-de-Gaulle and Orly, summed) and the main airport of each
  African city listed, with the city longitude/latitude.
- Source: Eurostat, dataset "avia_par_fr" (air passenger transport
  between the main airports of France and their main partner airports),
  measure PAS_CRD, annual values for 2024.
- Licence: Eurostat open data policy (free reuse with attribution).

## afrique_acp_cp1.geojson
- Geometry of African countries (WGS84) with the first-factor score
  ``cp1`` of a standardised principal component analysis on 42 countries,
  using demographic, social and economic indicators from the late 20th
  century. 42 countries carry a score; the rest are missing data.
- Source: ENSG L1 cartostat teaching material, practical TD3
  (https://github.com/fbxyz/ENSG_L1_cartostat). The factor score is
  recomputed here from the course indicator table (standardised PCA,
  first component). Geometry from the course topojson.

## helistations.csv
- Location of hospital helipads (mainland France), with night-flight
  capability derived from the "Night / IFR" column.
- Source: data.gouv.fr, dataset "Helistations hospitalieres".
- Licence: Creative Commons Attribution (CC-BY).

## relief_globe_ortho.tif
- Raster: Natural Earth I with Shaded Relief, Water, and Drainages
  (`NE1_LR_LC_SR_W_DR`, 10m), warped to the orthographic projection of the globe example by
  `docs/make_rasters.py`.
- Source: Natural Earth, https://www.naturalearthdata.com/
- Licence: public domain.

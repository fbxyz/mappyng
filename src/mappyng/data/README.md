# mappyng.data - Example GeoJSON Datasets

Ce module contient des données GeoJSON régionales et européennes qui servent d'exemples pour la bibliothèque mappyng.

## Datasets disponibles

### Données françaises

- **Régions françaises** (`abm_region_gen3.geojson`)
  - 145 KB
  - Contient les régions administratives françaises

- **Départements français** (`abm_pays_departement_gen3.geojson`)
  - 196 KB
  - Contient les départements français

### Données européennes

- **Pays européens** (`abm_pays_europe_gen3.geojson`)
  - 407 KB
  - Contient les pays européens avec codes ISO
  - Version détaillée

- **Pays européens simplifiés** (`abm_pays_europe_carto_gen3.geojson`)
  - 20 KB
  - Version simplifiée optimisée pour l'affichage cartographique

### Autres données

- **Régions EFS** (`efs_regionefs_gen3.geojson`)
  - 92 KB
  - Régions du secteur forestier européen (European Forest Sectors)

## Utilisation

### Chargement des données avec les fonctions helper

```python
from mappyng.data import (
    load_france_regions,
    load_france_departments,
    load_europe,
    load_europe_simplified,
    load_efs_regions
)

# Charger les régions françaises
regions = load_france_regions()

# Charger les départements
departments = load_france_departments()

# Charger les pays européens
europe = load_europe()

# Charger la version simplifiée des pays européens
europe_simple = load_europe_simplified()

# Charger les régions EFS
efs = load_efs_regions()
```

### Accès direct aux fichiers

```python
from mappyng.data import get_data_path
import geopandas as gpd

# Obtenir le chemin vers un fichier
path = get_data_path("abm_region_gen3.geojson")

# Charger manuellement avec geopandas
gdf = gpd.read_file(path)
```

### Lister les datasets disponibles

```python
from mappyng.data import list_datasets

datasets = list_datasets()
print(datasets)
# {
#     'france_regions': 'abm_region_gen3.geojson',
#     'france_departments': 'abm_pays_departement_gen3.geojson',
#     'europe': 'abm_pays_europe_gen3.geojson',
#     'europe_simplified': 'abm_pays_europe_carto_gen3.geojson',
#     'efs_regions': 'efs_regionefs_gen3.geojson'
# }
```

## Exemple complet

Les fichiers embarqués ne contiennent pas de statistiques (voir « Champs »
ci-dessous). L'exemple calcule donc la variable à cartographier, ici la
superficie de chaque département métropolitain, en Lambert-93 :

```python
import mappyng as mp
from mappyng.data import load_france_departments

gdf = load_france_departments()
gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()        # métropole
gdf["superficie_km2"] = gdf.to_crs(2154).area / 1e6

m = (
    mp.Map(gdf, width=800, height="auto", style="modern")
    + mp.Basemap()
    + mp.Choropleth(gdf, column="superficie_km2", method="Quantiles",
                    num_classes=5, cmap="Blues",
                    legend=mp.Legend("Superficie (km²)"))
    + mp.Title("Superficie des départements")
)
m.render("departements.svg")
```

## Champs

| Jeu | Entités | Champs |
|---|---|---|
| `france_regions` | 36 | `fid`, `LIB_GEO` (nom), `COD_GEO` (code), `valide` |
| `france_departments` | 103 | `fid`, `LIB_GEO`, `insee_reg`, `COD_GEO`, `valide` |
| `europe` | 94 | `pk_0`, `pk`, `fid`, `nom_pays`, `code_pays_iso3` |
| `europe_simplified` | 11 | `fid`, `nom_pays`, `code_pays_iso3` |
| `efs_regions` | 16 | `fid`, `LIB_GEO`, `COD_GEO`, `valide` |

Aucun jeu ne porte de colonne statistique : joindre les siennes sur
`COD_GEO` (ou `code_pays_iso3`).

## Format des données

Tous les fichiers GeoJSON sont au format standard avec :
- Géométries de type Polygon ou MultiPolygon
- Propriétés limitées aux identifiants et libellés ci-dessus
- Projection EPSG:3857 (Web Mercator) ; pour mesurer des surfaces ou des
  distances, reprojeter d'abord (`to_crs(2154)` pour la France)

## Provenance

État de la documentation au 2026-10-28. Les faits ci-dessous sont mesurés sur
les fichiers ; le reste est **inconnu** : le dépôt ne contient aucune trace
de l'origine des données (le premier commit qui les contient date de
2026-10-20 et ne renseigne pas la source).

| Jeu | Fichier | Entités | Sommets | Taille (Kio) |
|---|---|---:|---:|---:|
| `france_regions` | `abm_region_gen3.geojson` | 36 | 2,415 | 144 |
| `france_departments` | `abm_pays_departement_gen3.geojson` | 103 | 3,095 | 195 |
| `europe` | `abm_pays_europe_gen3.geojson` | 94 | 6,764 | 406 |
| `europe_simplified` | `abm_pays_europe_carto_gen3.geojson` | 11 | 476 | 19 |
| `efs_regions` | `efs_regionefs_gen3.geojson` | 16 | 1,547 | 91 |

| Information | État |
|---|---|
| Données de base | **IGN, GéoFLA, dernière édition** (indiqué par le mainteneur, non vérifié ici). GéoFLA ne couvre que la France : l'origine de `europe`, `europe_simplified` et `efs_regions` reste à préciser |
| Fonds généralisés | Réalisés par le mainteneur à partir de ces données : **pas de crédit pour la généralisation** (suffixe `gen3`) |
| URL de la source | https://www.data.gouv.fr/datasets/geofla-r (page consultée le 2026-10-28 ; dernière mise à jour de la page : 2026-09-10). IGN y indique que la production de GéoFLA est arrêtée et qu'il est remplacé par Admin Express |
| Millésime GéoFLA utilisé | **Inconnu** : la page ne donne pas de millésime ; à confirmer par le mainteneur |
| Date d'extraction | **Inconnue** |
| Licence de GéoFLA | « Licence Ouverte / Open Licence » (d'après la page data.gouv.fr ; version Etalab 1.0 ou 2.0 non précisée). Elle impose de citer la source et la date de mise à jour. Licence des jeux généralisés dérivés : **à confirmer** ; la licence MIT du package ne couvre pas les données |
| Méthode et tolérance de généralisation | **Non documentées** : le nombre de sommets ci-dessus donne le niveau de détail réel |
| Système de projection | EPSG:3857, lu dans le fichier |
| Champs | Voir « Champs » |

Les exemples citent « Source : IGN » : avec la Licence Ouverte, une mention plus
complète serait « Source : IGN, GéoFLA » suivie du millésime. À renseigner :
millésime GéoFLA, méthode de généralisation, licence des jeux dérivés, et
l'origine des jeux européens et EFS.

## Distribution

Les fichiers sont inclus dans le package via `package-data` dans
`pyproject.toml` (`"mappyng.data" = ["*.geojson", "README.md"]`) :
aucune configuration n'est nécessaire côté utilisateur.

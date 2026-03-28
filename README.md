# Portal Inmobiliario Scraper

---

## Español

Un scraper especializado para [Portal Inmobiliario](https://www.portalinmobiliario.com), el principal portal inmobiliario de Chile. Recopila avisos de arriendo de departamentos en las 346 comunas y 16 regiones del país, incluyendo precio, superficie, número de dormitorios/baños y ubicación.

No existe actualmente ninguna herramienta de código abierto equivalente para esta plataforma.

### Características

- Cubre las 346 comunas de Chile en 16 regiones
- Configurable por región o por comunas específicas desde la terminal
- Parsea precios en CLP y UF
- Maneja detección de bots con pausas aleatorias
- Guardado incremental — el progreso no se pierde si se interrumpe
- Omite tarjetas de edificios y avisos patrocinados

### Salida

Guarda un CSV en `data/raw/listings_YYYY_MM.csv` con las siguientes columnas:

| Columna | Descripción |
|---|---|
| `listing_id` | ID del aviso en Portal Inmobiliario (ej. `MLC-12345678`) |
| `price` | Precio del aviso (numérico) |
| `currency` | `UF` o `CLP` |
| `bedrooms` | Número de dormitorios |
| `bathrooms` | Número de baños |
| `m2` | Superficie en metros cuadrados |
| `location_raw` | Descripción de ubicación tal como aparece en el aviso (puede incluir dirección, barrio, metro cercano, etc.) |
| `commune` | Nombre estandarizado de la comuna |
| `url` | URL del aviso |
| `scrape_date` | Fecha UTC del scrape (`YYYY-MM-DD`) |

### Instalación

**Requisitos:** Python 3.10+

```bash
git clone https://github.com/cywu01/scraper-portal-inmobiliario.git
cd scraper-portal-inmobiliario
pip install -r requirements.txt
playwright install chromium
```

### Uso

**Scrapear todas las comunas de una región:**
```bash
python portal_inmobiliario.py --region metropolitana
python portal_inmobiliario.py --region valparaiso
```

**Scrapear comunas específicas por slug:**
```bash
python portal_inmobiliario.py --commune las-condes
python portal_inmobiliario.py --commune las-condes providencia nunoa
python portal_inmobiliario.py --commune santiago vitacura lo-barnechea
```

Los flags `--region` y `--commune` son mutuamente excluyentes: se debe usar uno u otro, no ambos.

**Autocompletado opcional:**
```bash
pip install argcomplete
eval "$(register-python-argcomplete portal_inmobiliario.py)"
```

### Limitaciones

- **Solo precios de oferta** — los precios reflejan los arriendos publicados, no contratos firmados
- **Solo departamentos** — no se incluyen casas, oficinas ni locales comerciales
- **Límite de paginación** — Portal Inmobiliario limita los resultados a ~42 páginas por búsqueda; comunas con mucha oferta pueden estar subrepresentadas
- **Sin autenticación** — los avisos detrás de inicio de sesión no son accesibles
- **Cambios en el sitio** — los selectores pueden dejar de funcionar si Portal Inmobiliario actualiza su estructura HTML

### Uso responsable

Esta herramienta está pensada para uso personal, de investigación y académico. Por favor respeta los términos de servicio de Portal Inmobiliario y evita ejecutar el scraper con alta frecuencia; el scraper ya incorpora pausas aleatorias entre solicitudes para minimizar el impacto sobre el sitio.

Esta herramienta no es oficial ni está afiliada a Portal Inmobiliario ni a su empresa matriz, Mercado Libre. El autor no tiene ninguna relación con ninguna de las dos compañías.

### Licencia

MIT

---

## English

A purpose-built scraper for [Portal Inmobiliario](https://www.portalinmobiliario.com), Chile's largest real estate listing platform. Collects apartment rental listings across all 346 communes and 16 regions of Chile, including price, size, bedroom/bathroom count, and location.

No equivalent open-source tool currently exists for this platform.

### Features

- Scrapes all 346 Chilean communes across 16 regions
- Configurable by region or specific communes via CLI
- Parses prices in both CLP and UF
- Handles bot detection with randomized delays
- Incremental saving — progress is not lost if interrupted
- Skips multi-unit building cards and sponsored listings

### Output

Saves a CSV to `data/raw/listings_YYYY_MM.csv` with the following columns:

| Column | Description |
|---|---|
| `listing_id` | Portal Inmobiliario listing ID (e.g. `MLC-12345678`) |
| `price` | Listing price (numeric) |
| `currency` | `UF` or `CLP` |
| `bedrooms` | Number of bedrooms |
| `bathrooms` | Number of bathrooms |
| `m2` | Surface area in square metres |
| `location_raw` | Location description as shown on the listing (may include street address, neighbourhood, nearby metro station, etc.) |
| `commune` | Standardised commune name |
| `url` | Listing URL |
| `scrape_date` | UTC date of scrape (`YYYY-MM-DD`) |

### Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/cywu01/scraper-portal-inmobiliario.git
cd scraper-portal-inmobiliario
pip install -r requirements.txt
playwright install chromium
```

### Usage

**Scrape all communes in a region:**
```bash
python portal_inmobiliario.py --region metropolitana
python portal_inmobiliario.py --region valparaiso
```

**Scrape specific communes by slug:**
```bash
python portal_inmobiliario.py --commune las-condes
python portal_inmobiliario.py --commune las-condes providencia nunoa
python portal_inmobiliario.py --commune santiago vitacura lo-barnechea
```

`--region` and `--commune` are mutually exclusive: use one or the other, not both.

**Optional: tab completion:**
```bash
pip install argcomplete
eval "$(register-python-argcomplete portal_inmobiliario.py)"
```

### Limitations

- **Asking prices only** — prices reflect listed rents, not signed contracts
- **Apartments only** — houses, offices, and commercial properties are not scraped
- **Pagination cap** — Portal Inmobiliario limits results to ~42 pages per search regardless of inventory; high-volume communes may be undercounted
- **No authentication** — listings behind login walls are not accessible
- **Site changes** — selectors may break if Portal Inmobiliario updates its HTML structure

### Responsible use

This tool is intended for personal, research, and academic use. Please respect Portal Inmobiliario's terms of service and avoid running the scraper at high frequency; randomized delays are built in to minimize load on the site.

This is not an official tool and is not affiliated with Portal Inmobiliario or its parent company, Mercado Libre. The author has no relationship with either company.

### License

MIT

---

## Referencia de slugs / Slug reference

Los slugs se usan como argumentos del flag `--commune` y como valores del flag `--region`. Cada sección muestra el nombre de la región y su slug correspondiente en el encabezado.

Slugs are used as arguments to the `--commune` flag and as values for the `--region` flag. Each section shows the region name and its corresponding slug in the header.

#### Arica y Parinacota — `arica-y-parinacota`

| Comuna | Slug |
|---|---|
| Arica | `arica` |
| Camarones | `camarones` |
| Putre | `putre` |
| General Lagos | `general-lagos` |

#### Tarapacá — `tarapaca`

| Comuna | Slug |
|---|---|
| Iquique | `iquique` |
| Alto Hospicio | `alto-hospicio` |
| Pozo Almonte | `pozo-almonte` |
| Camiña | `camina` |
| Colchane | `colchane` |
| Huara | `huara` |
| Pica | `pica` |

#### Antofagasta — `antofagasta`

| Comuna | Slug |
|---|---|
| Antofagasta | `antofagasta` |
| Mejillones | `mejillones` |
| Sierra Gorda | `sierra-gorda` |
| Taltal | `taltal` |
| Calama | `calama` |
| Ollagüe | `ollague` |
| San Pedro de Atacama | `san-pedro-de-atacama` |
| Tocopilla | `tocopilla` |
| María Elena | `maria-elena` |

#### Atacama — `atacama`

| Comuna | Slug |
|---|---|
| Copiapó | `copiapo` |
| Caldera | `caldera` |
| Tierra Amarilla | `tierra-amarilla` |
| Chañaral | `chanaral` |
| Diego de Almagro | `diego-de-almagro` |
| Vallenar | `vallenar` |
| Alto del Carmen | `alto-del-carmen` |
| Freirina | `freirina` |
| Huasco | `huasco` |

#### Coquimbo — `coquimbo`

| Comuna | Slug |
|---|---|
| La Serena | `la-serena` |
| Coquimbo | `coquimbo` |
| Andacollo | `andacollo` |
| La Higuera | `la-higuera` |
| Paiguano | `paiguano` |
| Vicuña | `vicuna` |
| Illapel | `illapel` |
| Canela | `canela` |
| Los Vilos | `los-vilos` |
| Salamanca | `salamanca` |
| Ovalle | `ovalle` |
| Combarbalá | `combarbala` |
| Monte Patria | `monte-patria` |
| Punitaqui | `punitaqui` |
| Río Hurtado | `rio-hurtado` |

#### Valparaíso — `valparaiso`

| Comuna | Slug |
|---|---|
| Valparaíso | `valparaiso` |
| Casablanca | `casablanca` |
| Concón | `concon` |
| Juan Fernández | `juan-fernandez` |
| Puchuncaví | `puchuncavi` |
| Quintero | `quintero` |
| Viña del Mar | `vina-del-mar` |
| Isla de Pascua | `isla-de-pascua` |
| Los Andes | `los-andes` |
| Calle Larga | `calle-larga` |
| Rinconada | `rinconada` |
| San Esteban | `san-esteban` |
| La Ligua | `la-ligua` |
| Cabildo | `cabildo` |
| Papudo | `papudo` |
| Petorca | `petorca` |
| Zapallar | `zapallar` |
| Quillota | `quillota` |
| Calera | `calera` |
| Hijuelas | `hijuelas` |
| La Cruz | `la-cruz` |
| Nogales | `nogales` |
| San Antonio | `san-antonio` |
| Algarrobo | `algarrobo` |
| Cartagena | `cartagena` |
| El Quisco | `el-quisco` |
| El Tabo | `el-tabo` |
| Santo Domingo | `santo-domingo` |
| San Felipe | `san-felipe` |
| Catemu | `catemu` |
| Llaillay | `llaillay` |
| Panquehue | `panquehue` |
| Putaendo | `putaendo` |
| Santa María | `santa-maria` |
| Limache | `limache` |
| Quilpué | `quilpue` |
| Villa Alemana | `villa-alemana` |
| Olmué | `olmue` |

#### Libertador Gral. Bernardo O'Higgins — `bernardo-ohiggins`

| Comuna | Slug |
|---|---|
| Rancagua | `rancagua` |
| Codegua | `codegua` |
| Coinco | `coinco` |
| Coltauco | `coltauco` |
| Doñihue | `donihue` |
| Graneros | `graneros` |
| Las Cabras | `las-cabras` |
| Machalí | `machali` |
| Malloa | `malloa` |
| Mostazal | `mostazal` |
| Olivar | `olivar` |
| Peumo | `peumo` |
| Pichidegua | `pichidegua` |
| Quinta de Tilcoco | `quinta-de-tilcoco` |
| Rengo | `rengo` |
| Requínoa | `requinoa` |
| San Vicente | `san-vicente` |
| Pichilemu | `pichilemu` |
| La Estrella | `la-estrella` |
| Litueche | `litueche` |
| Marchihue | `marchihue` |
| Navidad | `navidad` |
| Paredones | `paredones` |
| San Fernando | `san-fernando` |
| Chépica | `chepica` |
| Chimbarongo | `chimbarongo` |
| Lolol | `lolol` |
| Nancagua | `nancagua` |
| Palmilla | `palmilla` |
| Peralillo | `peralillo` |
| Placilla | `placilla` |
| Pumanque | `pumanque` |
| Santa Cruz | `santa-cruz` |

#### Maule — `maule`

| Comuna | Slug |
|---|---|
| Talca | `talca` |
| Constitución | `constitucion` |
| Curepto | `curepto` |
| Empedrado | `empedrado` |
| Maule | `maule` |
| Pelarco | `pelarco` |
| Pencahue | `pencahue` |
| Río Claro | `rio-claro` |
| San Clemente | `san-clemente` |
| San Rafael | `san-rafael` |
| Cauquenes | `cauquenes` |
| Chanco | `chanco` |
| Pelluhue | `pelluhue` |
| Curicó | `curico` |
| Hualañé | `hualane` |
| Licantén | `licanten` |
| Molina | `molina` |
| Rauco | `rauco` |
| Romeral | `romeral` |
| Sagrada Familia | `sagrada-familia` |
| Teno | `teno` |
| Vichuquén | `vichiquen` |
| Linares | `linares` |
| Colbún | `colbun` |
| Longaví | `longavi` |
| Parral | `parral` |
| Retiro | `retiro` |
| San Javier | `san-javier` |
| Villa Alegre | `villa-alegre` |
| Yerbas Buenas | `yerbas-buenas` |

#### Biobío — `biobio`

| Comuna | Slug |
|---|---|
| Concepción | `concepcion` |
| Coronel | `coronel` |
| Chiguayante | `chiguayante` |
| Florida | `florida` |
| Hualqui | `hualqui` |
| Lota | `lota` |
| Penco | `penco` |
| San Pedro de la Paz | `san-pedro-de-la-paz` |
| Santa Juana | `santa-juana` |
| Talcahuano | `talcahuano` |
| Tomé | `tome` |
| Hualpén | `hualpen` |
| Lebu | `lebu` |
| Arauco | `arauco` |
| Cañete | `canete` |
| Contulmo | `contulmo` |
| Curanilahue | `curanilahue` |
| Los Álamos | `los-alamos` |
| Tirúa | `tirua` |
| Los Ángeles | `los-angeles` |
| Antuco | `antuco` |
| Cabrero | `cabrero` |
| Laja | `laja` |
| Mulchén | `mulchen` |
| Nacimiento | `nacimiento` |
| Negrete | `negrete` |
| Quilaco | `quilaco` |
| Quilleco | `quilleco` |
| San Rosendo | `san-rosendo` |
| Santa Bárbara | `santa-barbara` |
| Tucapel | `tucapel` |
| Yumbel | `yumbel` |
| Alto Biobío | `alto-biobio` |

#### La Araucanía — `la-araucania`

| Comuna | Slug |
|---|---|
| Temuco | `temuco` |
| Carahue | `carahue` |
| Cunco | `cunco` |
| Curarrehue | `curarrehue` |
| Freire | `freire` |
| Galvarino | `galvarino` |
| Gorbea | `gorbea` |
| Lautaro | `lautaro` |
| Loncoche | `loncoche` |
| Melipeuco | `melipeuco` |
| Nueva Imperial | `nueva-imperial` |
| Padre Las Casas | `padre-las-casas` |
| Perquenco | `perquenco` |
| Pitrufquén | `pitrufquen` |
| Pucón | `pucon` |
| Saavedra | `saavedra` |
| Teodoro Schmidt | `teodoro-schmidt` |
| Toltén | `tolten` |
| Vilcún | `vilcun` |
| Villarrica | `villarrica` |
| Cholchol | `cholchol` |
| Angol | `angol` |
| Collipulli | `collipulli` |
| Curacautín | `curacautin` |
| Ercilla | `ercilla` |
| Lonquimay | `lonquimay` |
| Los Sauces | `los-sauces` |
| Lumaco | `lumaco` |
| Purén | `puren` |
| Renaico | `renaico` |
| Traiguén | `traiguen` |
| Victoria | `victoria` |

#### Los Ríos — `de-los-rios`

| Comuna | Slug |
|---|---|
| Valdivia | `valdivia` |
| Corral | `corral` |
| Lanco | `lanco` |
| Los Lagos | `los-lagos` |
| Máfil | `mafil` |
| Mariquina | `mariquina` |
| Paillaco | `paillaco` |
| Panguipulli | `panguipulli` |
| La Unión | `la-union` |
| Futrono | `futrono` |
| Lago Ranco | `lago-ranco` |
| Río Bueno | `rio-bueno` |

#### Los Lagos — `los-lagos`

| Comuna | Slug |
|---|---|
| Puerto Montt | `puerto-montt` |
| Calbuco | `calbuco` |
| Cochamó | `cochamo` |
| Fresia | `fresia` |
| Frutillar | `frutillar` |
| Los Muermos | `los-muermos` |
| Llanquihue | `llanquihue` |
| Maullín | `maullin` |
| Puerto Varas | `puerto-varas` |
| Castro | `castro` |
| Ancud | `ancud` |
| Chonchi | `chonchi` |
| Curaco de Vélez | `curaco-de-velez` |
| Dalcahue | `dalcahue` |
| Puqueldón | `puqueldon` |
| Queilén | `queilen` |
| Quellón | `quellon` |
| Quemchi | `quemchi` |
| Quinchao | `quinchao` |
| Osorno | `osorno` |
| Puerto Octay | `puerto-octay` |
| Purranque | `purranque` |
| Puyehue | `puyehue` |
| Río Negro | `rio-negro` |
| San Juan de la Costa | `san-juan-de-la-costa` |
| San Pablo | `san-pablo` |
| Chaitén | `chaiten` |
| Futaleufú | `futaleufu` |
| Hualaihué | `hualaihue` |
| Palena | `palena` |

#### Aysén — `aysen`

| Comuna | Slug |
|---|---|
| Coihaique | `coihaique` |
| Lago Verde | `lago-verde` |
| Aisén | `aisen` |
| Cisnes | `cisnes` |
| Guaitecas | `guaitecas` |
| Cochrane | `cochrane` |
| O'Higgins | `ohiggins` |
| Tortel | `tortel` |
| Chile Chico | `chile-chico` |
| Río Ibáñez | `rio-ibanez` |

#### Magallanes y de la Antártica Chilena — `magallanes-y-antartica-chilena`

| Comuna | Slug |
|---|---|
| Punta Arenas | `punta-arenas` |
| Laguna Blanca | `laguna-blanca` |
| Río Verde | `rio-verde` |
| San Gregorio | `san-gregorio` |
| Cabo de Hornos | `cabo-de-hornos` |
| Antártica | `antartica` |
| Porvenir | `porvenir` |
| Primavera | `primavera` |
| Timaukel | `timaukel` |
| Natales | `natales` |
| Torres del Paine | `torres-del-paine` |

#### Metropolitana de Santiago — `metropolitana`

| Comuna | Slug |
|---|---|
| Alhué | `alhue` |
| Buin | `buin` |
| Calera de Tango | `calera-de-tango` |
| Cerrillos | `cerrillos` |
| Cerro Navia | `cerro-navia` |
| Colina | `colina` |
| Conchalí | `conchali` |
| Curacaví | `curacavi` |
| El Bosque | `el-bosque` |
| El Monte | `el-monte` |
| Estación Central | `estacion-central` |
| Huechuraba | `huechuraba` |
| Independencia | `independencia` |
| Isla de Maipo | `isla-de-maipo` |
| La Cisterna | `la-cisterna` |
| La Florida | `la-florida` |
| La Granja | `la-granja` |
| La Pintana | `la-pintana` |
| La Reina | `la-reina` |
| Lampa | `lampa` |
| Las Condes | `las-condes` |
| Lo Barnechea | `lo-barnechea` |
| Lo Espejo | `lo-espejo` |
| Lo Prado | `lo-prado` |
| Macul | `macul` |
| Maipú | `maipu` |
| María Pinto | `maria-pinto` |
| Melipilla | `melipilla` |
| Ñuñoa | `nunoa` |
| Padre Hurtado | `padre-hurtado` |
| Paine | `paine` |
| Pedro Aguirre Cerda | `pedro-aguirre-cerda` |
| Peñaflor | `penaflor` |
| Peñalolén | `penalolen` |
| Pirque | `pirque` |
| Providencia | `providencia` |
| Pudahuel | `pudahuel` |
| Puente Alto | `puente-alto` |
| Quilicura | `quilicura` |
| Quinta Normal | `quinta-normal` |
| Recoleta | `recoleta` |
| Renca | `renca` |
| San Bernardo | `san-bernardo` |
| San Joaquín | `san-joaquin` |
| San José de Maipo | `san-jose-de-maipo` |
| San Miguel | `san-miguel` |
| San Pedro | `san-pedro` |
| San Ramón | `san-ramon` |
| Santiago | `santiago` |
| Talagante | `talagante` |
| Til Til | `til-til` |
| Vitacura | `vitacura` |

#### Ñuble — `nuble`

| Comuna | Slug |
|---|---|
| Chillán | `chillan` |
| Bulnes | `bulnes` |
| Chillán Viejo | `chillan-viejo` |
| El Carmen | `el-carmen` |
| Pemuco | `pemuco` |
| Pinto | `pinto` |
| Quillón | `quillon` |
| San Ignacio | `san-ignacio` |
| Yungay | `yungay` |
| Quirihue | `quirihue` |
| Cobquecura | `cobquecura` |
| Coelemu | `coelemu` |
| Ninhue | `ninhue` |
| Portezuelo | `portezuelo` |
| Ránquil | `ranquil` |
| Treguaco | `treguaco` |
| San Carlos | `san-carlos` |
| Coihueco | `coihueco` |
| Ñiquén | `niquen` |
| San Fabián | `san-fabian` |
| San Nicolás | `san-nicolas` |

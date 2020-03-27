# Coronavirus Disease 2019 (COVID-19 or 2019-nCoV) Cases Tracker

[This web map](https://app.isnew.info/covid-19) is an open source version of [the COVID-19 global cases website](https://arcg.is/0fHmTX) by [Johns Hopkins CSSE](https://systems.jhu.edu). It uses [OpenLayers](https://openlayers.org) for mapping, [Plotly.js](https://github.com/plotly/plotly.js) for plotting, and [Iconify](https://iconify.design/) for icons.

## UPDATES

As of March 27, 2020 at 6pm EDT, `fetch_data.py`'s count of the United States cases is 697 greater than CSSE's. I checked individual states and created the following table:
| County     | State | [CSSE CSV](https://github.com/CSSEGISandData/COVID-19/blob/master/csse_covid_19_data/csse_covid_19_daily_reports/03-26-2020.csv) | [CSSE REST](https://services9.arcgis.com/N9p5hsImWXAccRNI/arcgis/rest/services/Nc2JKvYFoAEOFCG5JSI6/FeatureServer/1/query?where=1%3D1&outFields=*&f=json) |
| -------------------- | ------------- | --: | --: |
| Coffee               | Alabama       |   1 |   0 |
| Fairbanks North Star | Alaska        |  11 |  10 |
| Cleburne             | Arkansas      |  47 |  46 |
| Dawson               | Georgia       |   3 |   2 |
| Unassigned           | Hawaii        |   8 |   6 |
| Bannock              | Idaho         |   3 |   2 |
| Bingham              | Idaho         |   2 |   1 |
| Unassigned           | Illinois      | 668 | N/A |
| LaSalle              | Illinois      |   3 |   0 |
| Logan                | Illinois      |   1 |   0 |
| Ascension            | Louisiana     |  91 |  90 |
| Morehouse            | Louisiana     |   3 |   2 |
| Jackson              | Michigan      |  17 |  16 |
| Newaygo              | Michigan      |   2 |   1 |
| Amite                | Mississippi   |   1 |   0 |
| Houston              | Tennessee     |   3 |   2 |
| Guadalupe            | Texas         |   9 |   8 |
| Walker               | Texas         |   3 |   2 |
| Unassigned           | Vermont       |   8 |   6 |
| Norfolk              | Virginia      |   9 |   8 |
| Fairfax City         | virginia      |   1 |   0 |
| Unassigned           | Washington    |  69 |  67 |
| Preston              | West Virginia |   2 |   1 |
| Ohio                 | West Virginia |   2 |   1 |
| Hancock              | West Virginia |   1 |   0 |

Data from the REST API is supposed to be current because their web map directly uses this data for visualization, but some of those numbers are decreasing for some counties in the United States. I have no idea which version to trust more between their daily reports vs. REST data.

## Data Sources

* Main data source: [CSSE](https://systems.jhu.edu)'s [time series data](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series) and [REST API](https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json)
* China: [DXY](https://ncov.dxy.cn/ncovh5/view/pneumonia)
* South Korea: [KCDC](http://ncov.mohw.go.kr/bdBoardList_Real.do)
* Italy: [StatisticheCoronavirus](https://statistichecoronavirus.it/regioni-coronavirus-italia/)
* Chile: [Dr. Javier Concha](https://sites.google.com/view/javierconcha)'s [COVID-19 Chile repository](https://github.com/javierconcha/covid-19-Chile/tree/master/data)

I found [CSSE](https://systems.jhu.edu)'s data unreliable because they keep changing country names and adding duplicate entries with incomplete records. I am trying to clean up their data as much as possible to avoid double counting (e.g., as of March 17, Guam vs. Guam, US and French Guiana vs. French Guiana, France), so there can be some discrepancy between my cleaned up data and their original data.

## Data Files

* geodata.json: GeoJSON file with case locations and time series data
* data.csv: CSV file with the same information in a tabular format

## Disclaimer

Data that `fetch_data.py` collects from various data sources is copyrighted by its original owners. Post-processing of the data by the script may introduce errors and the author is not responsible for any damages caused by using the processed data and the web map.

## License

Copyright (C) 2020, Huidae Cho <<https://idea.isnew.info>>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <<https://www.gnu.org/licenses/>>.

## Other Resources

* [Corona Data Scraper](https://coronadatascraper.com/)
* [Novel Coronavirus COVID-19 (2019-nCoV): Global Cases over time](https://covid19visualiser.com/)
* [Pandemic Estimator](https://pandemic-estimator.net/)
* [Tomas Pueyo's Model](https://medium.com/@tomaspueyo/coronavirus-act-today-or-people-will-die-f4d3d9cd99ca)

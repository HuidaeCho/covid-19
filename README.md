# Coronavirus Disease 2019 (COVID-19 or 2019-nCoV) Cases Tracker

[This web map](https://app.isnew.info/covid-19) is an open source version of [the COVID-19 global cases website](https://arcg.is/0fHmTX) by [Johns Hopkins CSSE](https://systems.jhu.edu). It uses [OpenLayers](https://openlayers.org) for mapping, [Plotly.js](https://github.com/plotly/plotly.js) for plotting, and [Iconify](https://iconify.design/) for icons.

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

## TODO

https://github.com/CSSEGISandData/COVID-19/issues/1250

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

# Coronavirus Disease 2019 (COVID-19 or 2019-nCoV) Cases Tracker

[This web map](https://app.isnew.info/covid-19) is an open source version of [the COVID-19 global cases website](https://arcg.is/0fHmTX) by [Johns Hopkins CSSE](https://systems.jhu.edu). It uses their [time series data](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series), [REST API](https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json), [DXY](https://ncov.dxy.cn/ncovh5/view/pneumonia), [KCDC](http://ncov.mohw.go.kr/bdBoardList_Real.do), and [OpenLayers](https://openlayers.org).

I found [CSSE](https://systems.jhu.edu)'s data unreliable because they keep changing country names and adding duplicate entries with incomplete records. I am trying to clean up their data as much as possible to avoid double counting (e.g., as of March 17, Guam vs. Guam, US and French Guiana vs. French Guiana, France), so there can be some discrepancy between my cleaned up data and their original data.

Also, remember that I am fetching data from [DXY](https://ncov.dxy.cn/ncovh5/view/pneumonia) and [KCDC](http://ncov.mohw.go.kr/bdBoardList_Real.do) every 30 minutes.

## Disclaimer

Data that `fetch_data.py` collects from [CSSE's website](https://gisanddata.maps.arcgis.com/apps/opsdashboard/index.html#/bda7594740fd40299423467b48e9ecf6) is copyrighted by [Johns Hopkins CSSE](https://systems.jhu.edu). Post-processing of the data by the script may introduce errors and the author is not responsible for any damages caused by using the processed data and the web map.

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

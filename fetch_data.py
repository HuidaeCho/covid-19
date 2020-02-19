#!/usr/bin/env python3
import requests
import io
import csv
import json
import datetime
import os
import config

features_url = 'https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

confirmed_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv'
recovered_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv'
deaths_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv'

geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'

geodata_json = 'geodata.json'

# download features from the REST server
res = requests.get(features_url)
features = json.loads(res.content)['features']

# create a new list for the output JSON object
data = []

# use this dictionary to avoid geocoding the same province multiple times
coors = {}

# download CSV files
confirmed_res = requests.get(confirmed_url)
recovered_res = requests.get(recovered_url)
deaths_res = requests.get(deaths_url)
with io.StringIO(confirmed_res.content.decode()) as confirmed_f,\
     io.StringIO(recovered_res.content.decode()) as recovered_f,\
     io.StringIO(deaths_res.content.decode()) as deaths_f:
    confirmed_reader = csv.reader(confirmed_f)
    recovered_reader = csv.reader(recovered_f)
    deaths_reader = csv.reader(deaths_f)

    # assume these header rows are all identical
    confirmed_header = confirmed_reader.__next__()
    recovered_header = recovered_reader.__next__()
    deaths_header = deaths_reader.__next__()

    # for each province
    for confirmed_row in confirmed_reader:
        recovered_row = recovered_reader.__next__()
        deaths_row = deaths_reader.__next__()

        if len(confirmed_row) == 0:
            continue
        col = 0
        province = confirmed_row[col]; col += 1
        country = confirmed_row[col]; col += 1
        # don't double-count; these records are now by city in the REST features
        if ((country == 'US' and
             province in ('Arizona', 'California', 'Illinois', 'Washington')) or
            (country == 'Canada' and province in ('Ontario'))) or \
           len(confirmed_row) < 3:
            continue

        # retrieve coordinates from the geocoding server if desired;
        # otherwise, just use coordinates from the spreadsheet
        if config.geocode:
            if province == '':
                location = country
                geocode_url = geocode_country_url.format(country=country)
            else:
                location = f'{country},{province}'
                geocode_url = geocode_province_url.format(country=country,
                        province=province)
            if not location in coors:
                res = requests.get(geocode_url, headers={
                    'referer': config.bing_maps_referer
                })
                ret = res.json()
                resources = ret['resourceSets'][0]['resources']
                if len(resources):
                    coor = resources[0]['geocodePoints'][0]['coordinates']
                    latitude = coor[0]
                    longitude = coor[1]
                else:
                    latitude = confirmed_row[3]
                    longitude = confirmed_row[4]
                coors[location] = {'latitude': latitude, 'longitude': longitude}
            else:
                latitude = coors[location].latitude
                longitude = coors[location].longitude
            col += 2
        else:
            latitude = confirmed_row[col]; col += 1
            longitude = confirmed_row[col]; col += 1

        # create and populate three lists with time series data
        confirmed = []
        recovered = []
        deaths = []
        for j in range(col, len(confirmed_row)):
            date = confirmed_header[j].split('/')
            time = datetime.datetime(2000 + int(date[2]), int(date[0]),
                    int(date[1]), 23, 59, tzinfo=datetime.timezone.utc)
            # YYYY/MM/DD UTC for iOS
            time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'
            confirmed.append({
                'time': time_str,
                'count': int(confirmed_row[j])
            })
            recovered.append({
                'time': time_str,
                'count': int(recovered_row[j])
            })
            deaths.append({
                'time': time_str,
                'count': int(deaths_row[j])
            })

        # try to find most up-to-date info from the REST server
        for feature in features:
            attr = feature['attributes']
            if country == 'Others' and attr['Province_State'] and \
               'Diamond Princess' in attr['Province_State']:
                province = attr['Province_State']
            # need an exact match
            if country != attr['Country_Region'] or \
               (province and province != attr['Province_State']):
                continue

            # grab new coordinates from the REST server
            latitude = feature['geometry']['y']
            longitude = feature['geometry']['x']

            last_updated = datetime.datetime.fromtimestamp(
                    attr['Last_Update']/1000, tz=datetime.timezone.utc)
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time > last_updated:
                last_updated = time
            last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
            confirmed.append({
                'time': last_updated_str,
                'count': int(attr['Confirmed'])
            }),
            recovered.append({
                'time': last_updated_str,
                'count': int(attr['Recovered'])
            }),
            deaths.append({
                'time': last_updated_str,
                'count': int(attr['Deaths'])
            })

        file = 'data/' + (province + ', ' if province else '') + country + '.csv'
        if os.path.exists(file):
            with open(file) as f:
                reader = csv.reader(f)
                reader.__next__()
                for row in reader:
                    last_updated = datetime.datetime.fromisoformat(row[0])
                    if last_updated > time:
                        last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
                        index = len(confirmed) - 1
                        confirmed[index] = {
                            'time': last_updated_str,
                            'count': int(row[1])
                        }
                        recovered[index] = {
                            'time': last_updated_str,
                            'count': int(row[2])
                        }
                        deaths[index] = {
                            'time': last_updated_str,
                            'count': int(row[3])
                        }

        data.append({
            'country': country,
            'province': province,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

    # try to find newly confirmed provinces from the REST server
    for feature in features:
        attr = feature['attributes']
        country = attr['Country_Region']
        province = attr['Province_State'] if attr['Province_State'] else ''
        latitude = feature['geometry']['y']
        longitude = feature['geometry']['x']
        # Diamond Princess is a country in the REST API, but it's a
        # province in Others in the CSV files; Others in the REST API is
        # empty!
        if country == 'Others':
            continue
        # need to skip existing provinces
        found = False
        for rec in data:
            if country == rec['country']:
                if province == rec['province'] or \
                   (not province and rec['province']) or \
                   (abs(latitude - rec['latitude']) < 0.00001 and
                    abs(longitude - rec['longitude']) < 0.00001):
                    if province and not rec['province']:
                        rec['province'] = province
                    found = True
                    break
        if found:
            continue

        # just found a new province that is not in the spreadsheet, but is in
        # the REST server; add this record
        last_updated = datetime.datetime.fromtimestamp(attr['Last_Update']/1000,
                tz=datetime.timezone.utc)
        last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
        confirmed = [{
            'time': last_updated_str,
            'count': int(attr['Confirmed'])
        }]
        recovered = [{
            'time': last_updated_str,
            'count': int(attr['Recovered'])
        }]
        deaths = [{
            'time': last_updated_str,
            'count': int(attr['Deaths'])
        }]
        data.append({
            'country': country,
            'province': province,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

# sort records by confirmed, country, and province
data = sorted(data, key=lambda x: (
    -x['confirmed'][len(x['confirmed'])-1]['count'],
    x['country'],
    x['province']))

# create a new list to store all the features
features = []
# create a feature collection
for i in range(0, len(data)):
    rec = data[i]
    features.append({
        'id': i,
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [rec['longitude'], rec['latitude']]
        },
        'properties': {
            'country': rec['country'],
            'province': rec['province'],
            'confirmed': rec['confirmed'],
            'recovered': rec['recovered'],
            'deaths': rec['deaths']
        }
    })

# finally, build the output GeoJSON object and save it
geodata = {
    'type': 'FeatureCollection',
    'features': features
}

f = open(geodata_json, 'w')
f.write(json.dumps(geodata))
f.close()

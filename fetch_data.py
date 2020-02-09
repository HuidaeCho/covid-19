#!/usr/bin/env python3
import requests
import pyexcel_ods3 as pyods
import json
import datetime
import config

data_url = 'https://docs.google.com/spreadsheets/d/1UF2pSkFTURko2OvfHWWlFpDFAr1UxCBA4JLwlSP6KFo/export?format=ods&id=1UF2pSkFTURko2OvfHWWlFpDFAr1UxCBA4JLwlSP6KFo'
features_url = 'https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'

data_ods = 'data.ods'
data_json = 'data.json'
features_json = 'features.json'
geodata_json = 'geodata.json'

res = requests.get(data_url)
if not b'unavailable' in res.content:
    f = open(data_ods, 'wb')
    f.write(res.content)
    f.close()
ods = pyods.get_data(data_ods)

res = requests.get(features_url)
f = open(features_json, 'wb')
f.write(res.content)
f.close()
features = json.loads(res.content)['features']

confirmed_sheet = ods['Confirmed']
recovered_sheet = ods['Recovered']
deaths_sheet = ods['Death']

headers = confirmed_sheet[0]

coors = {}
data = []

for i in range(1, len(confirmed_sheet)):
    cols = confirmed_sheet[i]
    if len(cols) == 0:
        continue
    country = cols[1]
    province = cols[0]
    # don't double-count; these records are now by city in the REST features
    if ((country == 'US' and
         province in ('Arizona', 'California', 'Illinois', 'Washington')) or
        (country == 'Canada' and province in ('Ontario'))) or len(cols) < 3:
        continue
    first_confirmed_date = cols[2]

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
                latitude = cols[3]
                longitude = cols[4]
            coors[location] = {'latitude': latitude, 'longitude': longitude}
        else:
            latitude = coors[location].latitude
            longitude = coors[location].longitude
    else:
        latitude = cols[3]
        longitude = cols[4]

    recovered_col = 5
    deaths_col = 5

    confirmed = []
    recovered = []
    deaths = []
    for j in range(5, len(cols)):
        atime = headers[j]

        count = cols[j]
        confirmed.append({
            'time': f'{atime}',
            'count': count
        })

        # some times are missing from the recovered sheet?
        found = False
        recovered_cols = recovered_sheet[i]
        for k in range(recovered_col, len(recovered_cols)):
            if atime == recovered_sheet[0][k]:
                found = True
                recovered_col = k + 1
                break
        count = recovered_cols[k] if found else ''
        recovered.append({
            'time': f'{atime}',
            'count': count
        })

        found = False
        deaths_cols = deaths_sheet[i]
        for k in range(deaths_col, len(deaths_cols)):
            if atime == deaths_sheet[0][k]:
                found = True
                deaths_col = k + 1
                break
        count = deaths_cols[k] if found else ''
        deaths.append({
            'time': f'{atime}',
            'count': count
        })
    for feature in features:
        attr = feature['attributes']
        if country == attr['Country_Region'] and country == 'Others':
            province = attr['Province_State']
        if country != attr['Country_Region'] or \
           (province and province != attr['Province_State']):
            continue
        last_updated = datetime.datetime.fromtimestamp(attr['Last_Update']/1000)
        if atime > last_updated:
            last_updated = atime
        confirmed.append({
            'time': f'{last_updated}',
            'count': attr['Confirmed']
        }),
        recovered.append({
            'time': f'{last_updated}',
            'count': attr['Recovered']
        }),
        deaths.append({
            'time': f'{last_updated}',
            'count': attr['Deaths']
        })
    data.append({
        'country': country,
        'province': province,
        'first_confirmed_date': f'{first_confirmed_date}',
        'latitude': latitude,
        'longitude': longitude,
        'confirmed': confirmed,
        'recovered': recovered,
        'deaths': deaths
    })

for feature in features:
    attr = feature['attributes']
    country = attr['Country_Region']
    province = attr['Province_State'] if attr['Province_State'] else ''
    latitude = feature['geometry']['y']
    longitude = feature['geometry']['x']
    found = False
    for rec in data:
        if country == rec['country']:
            if country == 'Others' or \
               province == rec['province'] or \
               (not province and rec['province']) or \
               (abs(latitude - rec['latitude']) < 0.00001 and
                abs(longitude - rec['longitude']) < 0.00001):
                if province and not rec['province']:
                    rec['province'] = province
                found = True
                break
    if found:
        continue
    last_updated = datetime.datetime.fromtimestamp(attr['Last_Update']/1000)
    confirmed = [{
        'time': f'{last_updated}',
        'count': attr['Confirmed']
    }]
    recovered = [{
        'time': f'{last_updated}',
        'count': attr['Recovered']
    }]
    deaths = [{
        'time': f'{last_updated}',
        'count': attr['Deaths']
    }]
    data.append({
        'country': country,
        'province': province,
        'first_confirmed_date': f'{last_updated}',
        'latitude': latitude,
        'longitude': longitude,
        'confirmed': confirmed,
        'recovered': recovered,
        'deaths': deaths
    })
data = sorted(data, key=lambda x: (
    -x['confirmed'][len(x['confirmed'])-1]['count'],
    x['country'],
    x['province'],
    x['first_confirmed_date']))

f = open(data_json, 'w')
f.write(json.dumps(data))
f.close()

features = []
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
            'first_confirmed_date': rec['first_confirmed_date'],
            'confirmed': rec['confirmed'],
            'recovered': rec['recovered'],
            'deaths': rec['deaths']
        }
    })

geodata = {
    'type': 'FeatureCollection',
    'features': features
}

f = open(geodata_json, 'w')
f.write(json.dumps(geodata))
f.close()

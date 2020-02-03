#!/usr/bin/env python3
import lxml.html
import requests
from config import bing_maps_key

jhu_scce_url = 'https://docs.google.com/spreadsheets/d/1yZv9w9zRKwrGTaR-YzmAqMefw4wMlaXocejdxZaTs6w/htmlview?usp=sharing&sle=true'
province_api_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={bing_maps_key}'
country_api_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={bing_maps_key}'

coors = {}

res = requests.get(jhu_scce_url)
root = lxml.html.fromstring(res.content)
for tab in root.iter('li'):
    day = tab.find('a').text
    table_id = tab.attrib['id'][13:]
    rows = root.xpath(f'//*[@id={table_id}]//table/tbody/tr')
    cols = rows[0].findall('td')
    country_ind = province_ind = updated_ind = suspected_ind = confirmed_ind = recovered_ind = deaths_ind = None
    for i in range(len(cols)):
        col = cols[i]
        if col.text is None:
            head = col.find('div').text
        else:
            head = col.text
        if head == 'Country' or head == 'Country/Region':
            country_ind = i
        elif head == 'Province/State':
            province_ind = i
        elif head == 'Last Update' or head == 'Date last updated':
            updated_ind = i
        elif head == 'Suspected':
            suspected_ind = i
        elif head == 'Confirmed':
            confirmed_ind = i
        elif head == 'Recovered':
            recovered_ind = i
        elif head == 'Deaths' or head == 'Demised':
            deaths_ind = i
    print('{"type": "FeatureCollection", "features": [')
    nrows = len(rows)
    for i in range(1, nrows):
        row = rows[i]
        cols = row.findall('td')
        country = cols[country_ind].text if country_ind is not None else None
        province = cols[province_ind].text if province_ind is not None else None
        updated = cols[updated_ind].text if updated_ind is not None else ''
        suspected = cols[suspected_ind].text if suspected_ind is not None else ''
        confirmed = cols[confirmed_ind].text if confirmed_ind is not None else ''
        recovered = cols[recovered_ind].text if recovered_ind is not None else ''
        deaths = cols[deaths_ind].text if deaths_ind is not None else ''
        if country is None:
            continue
        if province is None:
            api_url = country_api_url.format(country=country)
            location = country
            province = ''
        else:
            api_url = province_api_url.format(country=country, province=province)
            location = f'{country},{province}'
        if not location in coors:
            res = requests.get(api_url)
            json = res.json()
            coor = json['resourceSets'][0]['resources'][0]['geocodePoints'][0]['coordinates']
            coors[location] = {'lat': coor[0], 'lon': coor[1]}
        lat = coors[location]['lat']
        lon = coors[location]['lon']
        feature = f'{{"type": "Feature", "geometry": {{"type": "Point", "coordinates": [{lon}, {lat}]}}, "properties": {{"country": "{country}", "province": "{province}", "updated": "{updated}", "suspected": "{suspected}", "confirmed": "{confirmed}", "recovered": "{recovered}", "deaths": "{deaths}"}}}}'
        if i < nrows-1:
            print(f'{feature},')
        else:
            print(feature)
    print(']}')
    exit()

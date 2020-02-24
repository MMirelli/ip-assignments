import sqlite3
import json
import pprint


con = sqlite3.connect('test.db')
c = con.cursor()
c.execute("CREATE TABLE roads (client_id varchar(5) PRIMARY KEY, road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")
c.execute("CREATE TABLE roads (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id varchar(8), topic varchar(10), road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")

with open('data/1577541737.json', 'r') as myFile:
    data = myFile.read()

roads = json.loads(data)
print(roads)

for r in roads:
    c.execute("insert INTO roads(client_id, topic, road_name, data) values(?, ?, ?, ?)",
              ["5", "topic1", roads[0]['road_name'], roads[0]])
con.commit()





with open('part2/data/1577541737.json', 'r') as myFile:
  data = myFile.read()
obj = json.loads(data)
obj[0]
obj[1]
obj[3]
roads = json.loads(data)
roads
for r in roads:
    c.execute("CREATE TABLE roads (id varchar(3), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")
for r in roads:
    c.execute("CREATE TABLE roads (id INTEGER AUTOINCREMENT, road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")
    c.execute("DROP TABLE roads")
    c.execute("DROP TABLE roads")
    c.execute("CREATE TABLE roads (id INTEGER AUTOINCREMENT, road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")
    c.execute("CREATE TABLE roads (id INTEGER PRIMARY KEY AUTOINCREMENT, road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")
for r in roads:
    c.execute("insert INTO roads(road_name, data) values(?, ?)", [r['road_name'], json.dumps(r)])
for r in roads:
    c.execute('insert INTO roads(road_name, data) values(?, ?)', [r['road_name'], json.dumps(r)])

import readline
readline.write_history_file('./db_dataset.py')

import sqlite3
import json

con = sqlite3.connect('test.db')
c = con.cursor()

c.execute("DROP TABLE roads")

c.execute("CREATE TABLE roads (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id varchar(8), topic varchar(10), "
          "road_name varchar(60), data json, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)")

con.commit()

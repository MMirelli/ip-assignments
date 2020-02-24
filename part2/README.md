# broker start up (in part2/broker)
`docker-compose up`

# task1
`python sub_gen_complex.py --subN=4 --taskN=1`
`python pub.py --msgN=15 --taskN=1`

# task2
`python sub_gen_complex.py --subN=10 --taskN=2`
`python pub.py --msgN=15 --taskN=2`

# task3
`python sub_gen_complex.py --subN=16 --topicN=8 --taskN=3`
`python pub.py --msgN=5 --pubN=8 --taskN=3`

`sqlite3 <db_name>` # db_name is the db file in part2
		  # for more info (https://www.a2hosting.com/kb/developer-corner/sqlite/connect-to-sqlite-from-the-command-line)

> NB:
>    1. Always keep `topicN` = `pubN` (since each pubN has only 1 topic).
>    2. `subN` and `pubN` must be always even.

> For demo:
> `python sub_gen_complex.py --subN=8 --topicN=4 --taskN=3`
> `python pub.py --msgN=5 --pubN=4 --taskN=3`

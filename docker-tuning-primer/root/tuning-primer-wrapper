#!/bin/sh
listen="UNIX-LISTEN:/tmp/mysql.sock,fork,reuseaddr,unlink-early"
listen="${listen},user=mysql,group=mysql,mode=777"
socat "${listen}" "TCP:${MYSQL_PORT_3306_TCP_ADDR}:3306" &

/tuning-primer.sh "$@"

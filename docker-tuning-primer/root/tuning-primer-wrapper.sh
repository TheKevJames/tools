#!/bin/sh
socat UNIX-LISTEN:/tmp/mysql.sock,fork,reuseaddr,unlink-early,user=mysql,group=mysql,mode=777 \
      TCP:$MYSQL_PORT_3306_TCP_ADDR:3306 &

/tuning-primer.sh $@

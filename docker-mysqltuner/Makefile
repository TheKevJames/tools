VERSION=2.2.12

.PHONY: root/basic_passwords.txt root/mysqltuner.pl root/vulnerabilities.csv
all: root/basic_passwords.txt root/mysqltuner.pl root/vulnerabilities.csv

root/mysqltuner.pl:
	wget "https://raw.githubusercontent.com/major/MySQLTuner-perl/v$(VERSION)/$(notdir $@)" -O $@
root/basic_passwords.txt:
	wget "https://raw.githubusercontent.com/major/MySQLTuner-perl/v$(VERSION)/$(notdir $@)" -O $@
root/vulnerabilities.csv:
	wget "https://raw.githubusercontent.com/major/MySQLTuner-perl/v$(VERSION)/$(notdir $@)" -O $@

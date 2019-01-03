AMPY_OPTIONS=-b 115200 -p /dev/ttyUSB0
MAIN_SCRIPT=main.py

upload:
	$(shell \
		cd furnace_monitor; \
		files=$$(ls); \
		for file in $${files}; do \
			ampy $(AMPY_OPTIONS) rm $${file}; \
			ampy $(AMPY_OPTIONS) put $${file}; \
		done; \
		cd ..\
	)

ls:
	ampy $(AMPY_OPTIONS) ls

run:
	ampy $(AMPY_OPTIONS) run furnace_monitor/$(MAIN_SCRIPT)

format:
	@echo "**Formatting esp8266"
	@echo ""
	esptool.py --port /dev/ttyUSB0 erase_flash
	@echo ""

micropython:
	@echo "** Flashing micropython"
	@echo ""
	esptool.py --port /dev/ttyUSB0 --baud 460800 write_flash --flash_size=detect 0 ~/Downloads/esp8266-20180511-v1.9.4.bin
	sleep 3
	@echo ""

refresh: format micropython upload
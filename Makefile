PLAYLIST ?= https://www.youtube.com/playlist?list=PLS2yrp7IIPNj-GKemcb5p8IrIA7EUwvTE
PLAYLIST_NAME ?= playlist
MODE ?= talking-head
OUT ?= output

.PHONY: help test1 extract clean

help:
	@echo "Targets:"
	@echo "  make test1     - extract just the first video (sanity check)"
	@echo "  make extract   - extract the full playlist"
	@echo "  make clean     - remove output/ and distilled/"
	@echo ""
	@echo "Vars: PLAYLIST=<url>  MODE={talking-head,screen-heavy}  OUT=<dir>"

test1:
	python3 scripts/extract_playlist.py "$(PLAYLIST)" --mode $(MODE) --max-videos 1 --out $(OUT)

extract:
	python3 scripts/extract_playlist.py "$(PLAYLIST)" --mode $(MODE) --out $(OUT)

clean:
	rm -rf $(OUT) distilled

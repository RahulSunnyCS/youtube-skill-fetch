PLAYLIST ?= https://www.youtube.com/playlist?list=PLS2yrp7IIPNj-GKemcb5p8IrIA7EUwvTE
PLAYLIST_NAME ?= playlist
MODE ?= talking-head
OUT ?= output

.PHONY: help test1 extract preprocess phase2 quote-mine screenshots clean

help:
	@echo "Targets:"
	@echo "  make test1                  - extract just the first video (sanity check)"
	@echo "  make extract                - extract the full playlist"
	@echo "  make preprocess PLAYLIST_NAME=...  - clean transcripts before Phase 2"
	@echo "  make phase2 PLAYLIST_NAME=...      - distill cleaned transcripts via SDK"
	@echo "  make quote-mine PLAYLIST_NAME=... THEMES='a,b,c'  - local quote search"
	@echo "  make screenshots PLAYLIST_NAME=... - grab frames at 'look at this' moments"
	@echo "  make clean                  - remove output/ and distilled/"
	@echo ""
	@echo "Vars: PLAYLIST=<url>  PLAYLIST_NAME=<dir>  MODE={talking-head,screen-heavy}  OUT=<dir>"

test1:
	python3 scripts/extract_playlist.py "$(PLAYLIST)" --mode $(MODE) --max-videos 1 --out $(OUT)

extract:
	python3 scripts/extract_playlist.py "$(PLAYLIST)" --mode $(MODE) --out $(OUT)

preprocess:
	python3 scripts/preprocess_transcript.py --playlist $(PLAYLIST_NAME) --output-root $(OUT)

phase2:
	python3 scripts/run_phase2.py --playlist $(PLAYLIST_NAME) --output-root $(OUT)

quote-mine:
	python3 scripts/quote_mine.py --playlist $(PLAYLIST_NAME) --output-root $(OUT) --themes "$(THEMES)"

screenshots:
	python3 scripts/capture_screenshots.py --playlist $(PLAYLIST_NAME) --output-root $(OUT)

clean:
	rm -rf $(OUT) distilled

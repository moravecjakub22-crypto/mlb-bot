from flask import Flask
import threading
import requests
import time
import asyncio
from telegram import Bot

# --- FLASK (aby Render viděl port) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot běží"


# --- TELEGRAM + API ---
TOKEN = "8756274427:AAF2Jtbdc9V06tni871RweFT0dRMae8KXdg"
CHAT_ID = "5104285814"
ODDS_API_KEY = "7af756cdb9d6a15a834fa754bdefb245"

bot = Bot(token=TOKEN)

sent_games = set()
odds_data = []
odds_update_time = 0


# --- HLAVNÍ BOT ---
async def main():
    global odds_data, odds_update_time

    while True:
        print("BOT JEDE")

        try:
            schedule = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule?sportId=1",
		timeout=10
            ).json()

            if not schedule["dates"]:
                await asyncio.sleep(180)
                continue

            games = schedule["dates"][0]["games"]

            for game in games:
                game_id = game["gamePk"]

                live = requests.get(
                    f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live",
		timeout=10
                ).json()

                try:
                    linescore = live["liveData"]["linescore"]
                    boxscore = live["liveData"]["boxscore"]

                    inning = linescore["currentInning"]

                    # --- ODDS UPDATE ---
                    if 4 <= inning <= 5:
                        if time.time() - odds_update_time > 900:
                            print("🔄 Aktualizuji odds...")
                            try:
                                odds_data = requests.get(
                                    f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/ apiKey={ODDS_API_KEY}&regions=eu&markets=totals",
				timeout=10
                                ).json()
                            except:
                                odds_data = []
                            odds_update_time = time.time()

                    home = live["gameData"]["teams"]["home"]["name"]
                    away = live["gameData"]["teams"]["away"]["name"]

                    home_score = linescore["teams"]["home"]["runs"]
                    away_score = linescore["teams"]["away"]["runs"]

                    total_runs = home_score + away_score

                    home_hits = linescore["teams"]["home"]["hits"]
                    away_hits = linescore["teams"]["away"]["hits"]

                    home_bb = boxscore["teams"]["home"]["teamStats"]["batting"]["baseOnBalls"]
                    away_bb = boxscore["teams"]["away"]["teamStats"]["batting"]["baseOnBalls"]

                    home_lob = linescore["teams"]["home"]["leftOnBase"]
                    away_lob = linescore["teams"]["away"]["leftOnBase"]

                    home_traffic = home_hits + home_bb
                    away_traffic = away_hits + away_bb

                    # --- PITCH COUNT ---
                    home_pitchers = boxscore["teams"]["home"]["pitchers"]
                    away_pitchers = boxscore["teams"]["away"]["pitchers"]

                    home_pitch_count = 0
                    away_pitch_count = 0

                    if home_pitchers:
                        home_pitch_count = boxscore["teams"]["home"]["players"][f"ID{home_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    if away_pitchers:
                        away_pitch_count = boxscore["teams"]["away"]["players"][f"ID{away_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    # --- BULLPEN ---
                    home_bullpen = len(home_pitchers) > 1
                    away_bullpen = len(away_pitchers) > 1

                    # --- ODDS ---
                    best_over_odds = None
                    best_line = None

                    if odds_data:
                        for match in odds_data:
                            if home in match["home_team"] or away in match["away_team"]:
                                for bookmaker in match["bookmakers"]:
                                    for market in bookmaker["markets"]:
                                        if market["key"] == "totals":
                                            for outcome in market["outcomes"]:
                                                if outcome["name"] == "Over":
                                                    line = outcome["point"]
                                                    odds = outcome["price"]

                                                    if 6.5 <= line <= 8.5:
                                                        if best_over_odds is None or odds > best_over_odds:
                                                            best_over_odds = odds
                                                            best_line = line

                    pressure_team = away if away_traffic > home_traffic else home

                    # --- STRATEGIE ---
                    if (
                        4 <= inning <= 5
                        and total_runs <= 4
                        and abs(home_score - away_score) <= 3
                        and (home_lob >= 3 and home_traffic >= 6)
                        and (away_lob >= 2 and away_traffic >= 4)
                        and (home_pitch_count >= 60 or away_pitch_count >= 60)
                        and (home_bullpen or away_bullpen)
                        and (best_over_odds is None or best_over_odds >= 1.7)
                        and game_id not in sent_games
                    ):
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=(
                                f"🔥 OVER VALUE BET\n\n"
                                f"{away} vs {home}\n"
                                f"Score: {away_score} - {home_score}\n"
                                f"Inning: {inning}\n\n"
                                f"Line: {best_line if best_line else 'N/A'}\n"
                                f"Odds: {best_over_odds if best_over_odds else 'N/A'}\n\n"
                                f"LOB: {away_lob} - {home_lob}\n"
                                f"Traffic: {away_traffic} - {home_traffic}\n"
                                f"Pitch: {away_pitch_count} - {home_pitch_count}\n"
                                f"Bullpen: YES\n"
                                f"🔥 Pressure: {pressure_team}\n\n"
                                f"💣 TLAK + UNAVA + BULLPEN → OVER"
                            )
                        )

                        sent_games.add(game_id)

                except Exception as e:
                    print("ERROR GAME:", e)

        except Exception as e:
            print("ERROR LOOP:", e)

        await asyncio.sleep(180)


# --- FIX PRO RENDER (ASYNC LOOP) ---
def start_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


def run_web():
    app.run(host="0.0.0.0", port=10000)


# --- START ---
threading.Thread(target=run_web).start()
threading.Thread(target=start_async_loop).start()

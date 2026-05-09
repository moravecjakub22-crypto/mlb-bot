from flask import Flask
import threading
import requests
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT běží"


# --- API ---
TOKEN = "8756274427:AAF2Jtbdc9V06tni871RweFT0dRMae8KXdg"
CHAT_ID = "5104285814"
ODDS_API_KEY = "7af756cdb9d6a15a834fa754bdefb245"

sent_games = set()
odds_data = []
last_odds_update = 0


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("TELEGRAM ERROR:", e)


# --- MIN ODDS ---
def get_min_odds(score):
    if score >= 9:
        return 1.6
    if score == 8:
        return 1.7
    if score == 7:
        return 1.8
    if score == 6:
        return 1.9
    return None


def main():
    global odds_data, last_odds_update

    while True:
        print("BOT JEDE")

        try:
            schedule = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule?sportId=1",
                timeout=10
            ).json()

            if not schedule.get("dates"):
                time.sleep(120)
                continue

            games = schedule["dates"][0]["games"]

            for game in games:
                game_id = game["gamePk"]

                try:
                    live = requests.get(
                        f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live",
                        timeout=10
                    ).json()

                    linescore = live["liveData"]["linescore"]
                    boxscore = live["liveData"]["boxscore"]

                    if not linescore or "currentInning" not in linescore:
                        continue

                    inning = linescore["currentInning"]

                    # 👉 jen mid game
                    if inning < 5 or inning > 7:
                        continue

                    home = live["gameData"]["teams"]["home"]["name"]
                    away = live["gameData"]["teams"]["away"]["name"]

                    home_score = linescore["teams"]["home"]["runs"]
                    away_score = linescore["teams"]["away"]["runs"]
                    total_runs = home_score + away_score

                    home_hits = linescore["teams"]["home"]["hits"]
                    away_hits = linescore["teams"]["away"]["hits"]

                    home_bb = boxscore["teams"]["home"]["teamStats"]["batting"]["baseOnBalls"]
                    away_bb = boxscore["teams"]["away"]["teamStats"]["batting"]["baseOnBalls"]

                    home_traffic = home_hits + home_bb
                    away_traffic = away_hits + away_bb

                    home_pitchers = boxscore["teams"]["home"]["pitchers"]
                    away_pitchers = boxscore["teams"]["away"]["pitchers"]

                    home_pitch = 0
                    away_pitch = 0

                    if home_pitchers:
                        home_pitch = boxscore["teams"]["home"]["players"][f"ID{home_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    if away_pitchers:
                        away_pitch = boxscore["teams"]["away"]["players"][f"ID{away_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    home_bullpen = len(home_pitchers) > 1
                    away_bullpen = len(away_pitchers) > 1

                    # --- SCORING ---
                    score = 0

                    if total_runs <= 6:
                        score += 1

                    if abs(home_score - away_score) <= 3:
                        score += 1

                    if home_traffic >= 5:
                        score += 2

                    if away_traffic >= 5:
                        score += 2

                    if home_pitch >= 60:
                        score += 1

                    if away_pitch >= 60:
                        score += 1

                    if home_bullpen:
                        score += 1

                    if away_bullpen:
                        score += 1

                    print(f"{home} vs {away} | inning {inning} | score {score}")

                    # 👉 jen silné situace
                    if score < 7:
                        continue

                    # 🔄 ODDS update každých 30 min
                    if time.time() - last_odds_update > 1800:
                        print("Aktualizuji odds...")
                        try:
                            odds_data = requests.get(
                                f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals",
                                timeout=10
                            ).json()
                        except:
                            odds_data = []

                        last_odds_update = time.time()

                    # 🔎 NAJDI ODDS
                    best_odds = None
                    best_line = None

                    for match in odds_data:
                        if home in match.get("home_team", "") or away in match.get("away_team", ""):
                            for bookmaker in match.get("bookmakers", []):
                                for market in bookmaker.get("markets", []):
                                    if market.get("key") == "totals":
                                        for outcome in market.get("outcomes", []):
                                            if outcome.get("name") == "Over":
                                                odds = outcome.get("price")
                                                line = outcome.get("point")

                                                if odds:
                                                    if best_odds is None or odds > best_odds:
                                                        best_odds = odds
                                                        best_line = line

                    min_odds = get_min_odds(score)

                    print(f"ODDS: {best_odds} | MIN: {min_odds}")

                    # 🚀 VALUE + FALLBACK LOGIKA
                    if game_id not in sent_games:

                        # 💰 VALUE MODE
                        if best_odds and min_odds:
                            if best_odds >= min_odds:
                                mode = "💰 VALUE"
                            else:
                                continue

                        # ⚡ NO ODDS MODE
                        else:
                            if score < 8:
                                continue
                            mode = "⚡ NO ODDS"

                        level = "💎" if score >= 8 else "🔥"

                        send_telegram(
                            f"{mode} {level} OVER\n\n"
                            f"{home} vs {away}\n"
                            f"Score: {home_score}-{away_score}\n"
                            f"Inning: {inning}\n\n"
                            f"Bot Score: {score}\n"
                            f"Line: {best_line if best_line else 'N/A'}\n"
                            f"Odds: {best_odds if best_odds else 'N/A'}\n"
                            f"Min Odds: {min_odds if min_odds else 'N/A'}\n\n"
                            f"Traffic: {home_traffic}-{away_traffic}\n"
                            f"Pitch: {home_pitch}-{away_pitch}\n"
                            f"Bullpen: YES"
                        )

                        sent_games.add(game_id)

                except Exception as e:
                    print("ERROR GAME:", e)

        except Exception as e:
            print("ERROR LOOP:", e)

        time.sleep(120)


# --- START ---
threading.Thread(target=main, daemon=True).start()
app.run(host="0.0.0.0", port=10000)

from flask import Flask
import threading
import requests
import time

# --- FLASK ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot běží"


# --- API KLÍČE ---
TOKEN = "8756274427:AAF2Jtbdc9V06tni871RweFT0dRMae8KXdg"
CHAT_ID = "5104285814"

sent_games = set()


# --- TELEGRAM ---
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


# --- HLAVNÍ BOT ---
def main():
    while True:
        print("BOT JEDE")

        try:
            schedule = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule?sportId=1",
                timeout=10
            ).json()

            # 🔍 DEBUG
            print("DATES:", len(schedule.get("dates", [])))

            if not schedule.get("dates"):
                print("Žádné zápasy")
                time.sleep(120)
                continue

            # 🔥 vezmeme VŠECHNY zápasy
            games = []
            for date in schedule["dates"]:
                for game in date["games"]:
                    games.append(game)

            print("NALEZENO ZÁPASŮ:", len(games))

            for game in games:
                game_id = game["gamePk"]

                live = requests.get(
                    f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live",
                    timeout=10
                ).json()

                try:
                    status = live["gameData"]["status"]["abstractGameState"]
                    print("STATUS:", status)

                    # 🔥 LIVE + IN PROGRESS
                    if status not in ["Live", "In Progress"]:
                        continue

                    linescore = live["liveData"]["linescore"]
                    boxscore = live["liveData"]["boxscore"]

                    inning = linescore.get("currentInning", 0)

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

                    # --- PITCH ---
                    home_pitchers = boxscore["teams"]["home"]["pitchers"]
                    away_pitchers = boxscore["teams"]["away"]["pitchers"]

                    home_pitch = 0
                    away_pitch = 0

                    if home_pitchers:
                        home_pitch = boxscore["teams"]["home"]["players"][f"ID{home_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    if away_pitchers:
                        away_pitch = boxscore["teams"]["away"]["players"][f"ID{away_pitchers[0]}"]["stats"]["pitching"]["pitchesThrown"]

                    # --- BULLPEN ---
                    home_bullpen = len(home_pitchers) > 1
                    away_bullpen = len(away_pitchers) > 1

                    # --- SCORING ---
                    score = 0

                    if 4 <= inning <= 7:
                        score += 1

                    if total_runs <= 6:
                        score += 1

                    if abs(home_score - away_score) <= 4:
                        score += 1

                    if home_traffic >= 4:
                        score += 2

                    if away_traffic >= 4:
                        score += 2

                    if home_pitch >= 60:
                        score += 1

                    if away_pitch >= 60:
                        score += 1

                    if home_bullpen:
                        score += 1

                    if away_bullpen:
                        score += 1

                    # 🔍 DEBUG
                    print(f"{away} vs {home} | inning {inning} | score {score}")

                    # --- SIGNAL ---
                    if score >= 5 and game_id not in sent_games:
                        send_telegram(
                            f"🔥 OVER SIGNAL (Score: {score})\n\n"
                            f"{away} vs {home}\n"
                            f"Score: {away_score} - {home_score}\n"
                            f"Inning: {inning}\n\n"
                            f"Traffic: {away_traffic} - {home_traffic}\n"
                            f"Pitch: {away_pitch} - {home_pitch}\n"
                            f"Bullpen: YES\n"
                        )

                        sent_games.add(game_id)

                except Exception as e:
                    print("ERROR GAME:", e)

        except Exception as e:
            print("ERROR LOOP:", e)

        time.sleep(120)  # ⏱️ kontrola každé 2 min


# --- START ---
threading.Thread(target=main).start()
app.run(host="0.0.0.0", port=10000)

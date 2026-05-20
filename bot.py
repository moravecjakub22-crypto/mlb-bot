from flask import Flask
import threading
import requests
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "BOT běží"


# =========================
# TELEGRAM + API
# =========================

TOKEN = "8756274427:AAF2Jtbdc9V06tni871RweFT0dRMae8KXdg"
CHAT_ID = "5104285814"
ODDS_API_KEY = "7af756cdb9d6a15a834fa754bdefb245"

sent_games = set()

odds_data = []
last_odds_update = 0


# =========================
# TELEGRAM
# =========================

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


# =========================
# MIN ODDS
# =========================

def get_min_odds(score):

    if score >= 10:
        return 1.70

    if score == 9:
        return 1.80

    if score == 8:
        return 1.90

    return None


# =========================
# MAIN BOT
# =========================

def main():

    global odds_data
    global last_odds_update

    while True:

        print("BOT JEDE - kontrola zápasů")

        try:

            schedule = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule?sportId=1",
                timeout=15
            ).json()

            if not schedule.get("dates"):

                print("Žádné zápasy")
                time.sleep(120)
                continue

            games = schedule["dates"][0]["games"]

            for game in games:

                game_id = game["gamePk"]

                try:

                    live = requests.get(
                        f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live",
                        timeout=15
                    ).json()

                    linescore = live["liveData"]["linescore"]
                    boxscore = live["liveData"]["boxscore"]

                    if not linescore:
                        continue

                    if "currentInning" not in linescore:
                        continue

                    inning = linescore["currentInning"]

                    # =========================
                    # INNING FILTER
                    # =========================

                    if inning < 5 or inning > 7:
                        continue

                    # =========================
                    # TEAMS
                    # =========================

                    home = live["gameData"]["teams"]["home"]["name"]
                    away = live["gameData"]["teams"]["away"]["name"]

                    # =========================
                    # SCORE
                    # =========================

                    home_score = linescore["teams"]["home"].get("runs", 0)
                    away_score = linescore["teams"]["away"].get("runs", 0)

                    total_runs = home_score + away_score

                    # =========================
                    # HITS
                    # =========================

                    home_hits = linescore["teams"]["home"].get("hits", 0)
                    away_hits = linescore["teams"]["away"].get("hits", 0)

                    # =========================
                    # WALKS
                    # =========================

                    home_bb = (
                        boxscore["teams"]["home"]
                        .get("teamStats", {})
                        .get("batting", {})
                        .get("baseOnBalls", 0)
                    )

                    away_bb = (
                        boxscore["teams"]["away"]
                        .get("teamStats", {})
                        .get("batting", {})
                        .get("baseOnBalls", 0)
                    )

                    home_traffic = home_hits + home_bb
                    away_traffic = away_hits + away_bb

                    # =========================
                    # PITCHERS
                    # =========================

                    home_pitchers = boxscore["teams"]["home"].get("pitchers", [])
                    away_pitchers = boxscore["teams"]["away"].get("pitchers", [])

                    home_pitch = 0
                    away_pitch = 0

                    try:

                        if home_pitchers:

                            home_pitch = (
                                boxscore["teams"]["home"]["players"][f"ID{home_pitchers[0]}"]
                                .get("stats", {})
                                .get("pitching", {})
                                .get("pitchesThrown", 0)
                            )

                        if away_pitchers:

                            away_pitch = (
                                boxscore["teams"]["away"]["players"][f"ID{away_pitchers[0]}"]
                                .get("stats", {})
                                .get("pitching", {})
                                .get("pitchesThrown", 0)
                            )

                    except Exception as e:

                        print("PITCH ERROR:", e)

                        home_pitch = 0
                        away_pitch = 0

                    # =========================
                    # BULLPEN
                    # =========================

                    home_bullpen = len(home_pitchers) > 1
                    away_bullpen = len(away_pitchers) > 1

                    # =========================
                    # SCORING
                    # =========================

                    score = 0

                    # close game
                    if abs(home_score - away_score) <= 3:
                        score += 1

                    # low scoring
                    if total_runs <= 6:
                        score += 1

                    # traffic
                    if home_traffic >= 5:
                        score += 2

                    if away_traffic >= 5:
                        score += 2

                    # tired pitchers
                    if home_pitch >= 60:
                        score += 1

                    if away_pitch >= 60:
                        score += 1

                    # bullpen
                    if home_bullpen:
                        score += 1

                    if away_bullpen:
                        score += 1

                    print(
                        f"{home} vs {away} | "
                        f"Inning {inning} | "
                        f"Bot Score {score}"
                    )

                    # =========================
                    # ONLY DIAMOND
                    # =========================

                    if score < 8:
                        continue

                    # =========================
                    # UPDATE ODDS
                    # =========================

                    if time.time() - last_odds_update > 1800:

                        print("Aktualizuji odds...")

                        try:

                            odds_data = requests.get(
                                f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals",
                                timeout=15
                            ).json()

                            print("Odds aktualizovány")

                        except Exception as e:

                            print("ODDS ERROR:", e)
                            odds_data = []

                        last_odds_update = time.time()

                    # =========================
                    # FIND BEST ODDS
                    # =========================

                    best_odds = None
                    best_line = None

                    for match in odds_data:

                        if (
                            home in match.get("home_team", "")
                            or away in match.get("away_team", "")
                        ):

                            for bookmaker in match.get("bookmakers", []):

                                for market in bookmaker.get("markets", []):

                                    if market.get("key") == "totals":

                                        for outcome in market.get("outcomes", []):

                                            if outcome.get("name") == "Over":

                                                odds = outcome.get("price")
                                                line = outcome.get("point")

                                                if odds and line:

                                                    if (
                                                        best_odds is None
                                                        or odds > best_odds
                                                    ):

                                                        best_odds = odds
                                                        best_line = line

                    min_odds = get_min_odds(score)

                    print(
                        f"ODDS {best_odds} | "
                        f"LINE {best_line} | "
                        f"MIN {min_odds}"
                    )

                    # =========================
                    # VALUE FILTER
                    # =========================

                    if game_id not in sent_games:

                        if best_odds and min_odds and best_line:

                            if (
                                best_odds >= min_odds
                                and best_odds <= 3
                                and best_line > total_runs
                            ):

                                mode = "💰 VALUE"

                            else:
                                continue

                        else:
                            continue

                        # =========================
                        # LEVEL
                        # =========================

                        level = "💎"

                        # =========================
                        # TELEGRAM MESSAGE
                        # =========================

                        send_telegram(

                            f"{mode} {level} OVER\n\n"

                            f"{home} vs {away}\n"
                            f"Score: {home_score}-{away_score}\n"
                            f"Inning: {inning}\n\n"

                            f"Bot Score: {score}\n"
                            f"Line: {best_line}\n"
                            f"Odds: {best_odds}\n"
                            f"Min Odds: {min_odds}\n\n"

                            f"Traffic: {home_traffic}-{away_traffic}\n"
                            f"Pitch: {home_pitch}-{away_pitch}\n"
                            f"Bullpen: YES"
                        )

                        sent_games.add(game_id)

                except Exception as e:

                    print("ERROR GAME:", e)
                    time.sleep(1)

        except Exception as e:

            print("ERROR LOOP:", e)
            time.sleep(10)

        time.sleep(120)


# =========================
# START
# =========================

threading.Thread(
    target=main,
    daemon=True
).start()

app.run(
    host="0.0.0.0",
    port=10000
)

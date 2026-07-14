import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_uploader import authenticate
from googleapiclient.discovery import build
from clip_analyzer import save_performance, VideoPerformance, PERF_DB_PATH


def fetch_all_stats() -> list:
    creds = authenticate()
    if not creds:
        print("Sem credenciais")
        return []

    youtube = build("youtube", "v3", credentials=creds)

    # Use known video IDs from our uploads
    known_ids = [
        "EmtYPKxfvZw", "85Y0ffwr7tY", "1ifj_1kiIEQ", "PwnUfdzAmUQ",
        "QfzURjNmyj0", "GPCqkFjoHts", "L7YSDBsZAeQ", "Fb8al4VQObU",
        "0PWVkv8ZrNE", "v-UF6EDw9uY", "t-T39gRN68M", "YER_uh8S_JY",
        "7r9PF2kQsxU", "iUlfOg0guZ4", "qXqL5c_fO6U", "nFxDvn85nHs",
        "bI3WhDbCY90", "8RUVpFv3ZLk", "ZqNPJjLodX4", "r8wCZJexi2w",
        "ak46GTOFRAM"
    ]
    video_ids = known_ids

    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        vreq = youtube.videos().list(part="statistics,snippet", id=",".join(batch))
        vresp = vreq.execute()
        for item in vresp.get("items", []):
            stats = item.get("statistics", {})
            vid = item["id"]
            title = item.get("snippet", {}).get("title", "")
            vp = VideoPerformance(
                video_id=vid,
                title=title,
                views_total=int(stats.get("viewCount", 0)),
                likes=int(stats.get("likeCount", 0)),
                comments=int(stats.get("commentCount", 0)),
            )
            if vp.views_total > 0:
                vp.like_ratio = vp.likes / vp.views_total * 100
            save_performance(vid, vp)
            results.append(vp)

    return results


def print_summary(results: list):
    results.sort(key=lambda x: x.views_total, reverse=True)
    print(f"{'Video ID':12s} {'Views':>6s} {'Likes':>4s} {'Ratio':>5s} {'Title':30s}")
    print("-"*70)
    for r in results:
        t = r.title[:28] if r.title else "?"
        print(f"{r.video_id:12s} {r.views_total:6d} {r.likes:4d} {r.like_ratio:4.1f}% {t:30s}")

    if results:
        avg_v = sum(r.views_total for r in results) / len(results)
        avg_l = sum(r.likes for r in results) / len(results)
        best = max(results, key=lambda x: x.views_total)
        print(f"\nMedia: {avg_v:.0f} views, {avg_l:.1f} likes")
        print(f"Melhor: {best.title} ({best.video_id}) - {best.views_total} views")

        # Check the features DB
        from clip_analyzer import FEATURES_DB_PATH
        if os.path.exists(FEATURES_DB_PATH):
            with open(FEATURES_DB_PATH) as f:
                features_db = json.load(f)
            print(f"\nClipes analisados: {len(features_db)}")
            # Correlate top performers with features
            high_view = [r for r in results if r.views_total >= 10]
            if len(high_view) >= 2:
                print(f"Top {len(high_view)} clipes tem >= 10 views")


if __name__ == "__main__":
    print("Buscando stats do YouTube...")
    results = fetch_all_stats()
    print_summary(results)
    print(f"\nDados salvos em: {PERF_DB_PATH}")

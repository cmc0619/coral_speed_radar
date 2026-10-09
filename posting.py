"""Optional publication using Tweepy's X API v2 client."""
import os


def post_to_x(event):
    if not event["plate"]:
        raise ValueError("Cannot publish a plate without OCR consensus")
    import tweepy
    names = ("X_CONSUMER_KEY", "X_CONSUMER_SECRET",
             "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    credentials = [os.getenv(key) for key in names]
    if not all(credentials):
        raise RuntimeError("X API credentials missing")
    client = tweepy.Client(consumer_key=credentials[0],
                           consumer_secret=credentials[1],
                           access_token=credentials[2],
                           access_token_secret=credentials[3])
    response = client.create_tweet(
        text="Plate {} — estimated {:.1f} mph, {}bound. "
             "Unverified camera-based estimate.".format(
                 event["plate"], event["speed_mph"], event["direction"]))
    if not response or not response.data or not response.data.get("id"):
        raise RuntimeError("X did not acknowledge the post")
    return response.data["id"]

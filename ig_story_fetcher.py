import sys
import logging
import tomllib
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from glob import glob
from tempfile import TemporaryDirectory
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from moviepy.editor import VideoFileClip, concatenate_videoclips

import boto3
from botocore.client import Config

logger = logging.getLogger()


def login_user(
    client: Client, username: str, password: str, session_file: Path
) -> None:
    """
    Attempts to login to Instagram using either the provided session information
    or the provided username and password.
    """
    if session_file.exists():
        session = client.load_settings(session_file)
    else:
        session = None
        session_file.parent.mkdir(parents=True, exist_ok=True)

    login_via_session = False
    login_via_pw = False

    if session:
        try:
            client.set_settings(session)
            client.login(username, password)

            # check if session is valid
            try:
                client.get_timeline_feed()
            except LoginRequired:
                logger.info(
                    "Session is invalid, need to login via username and password"
                )

                old_session = client.get_settings()

                # use the same device uuids across logins
                client.set_settings({})
                client.set_uuids(old_session["uuids"])

                client.login(username, password)
            login_via_session = True
        except Exception as e:
            logger.info("Couldn't login user using session information: %s" % e)

    if not login_via_session:
        try:
            logger.info(
                "Attempting to login via username and password. username: %s" % username
            )
            if client.login(username, password):
                login_via_pw = True
                client.dump_settings(session_file)
        except Exception as e:
            logger.info("Couldn't login user using username and password: %s" % e)


def concatenate_stories(stories_dir: str, video_filename: str) -> None:
    stories = []
    for story in sorted(glob(f"{stories_dir}/*.mp4")):
        stories.append(VideoFileClip(story))

    merged_clip = concatenate_videoclips(stories)
    merged_clip.write_videofile(video_filename)


def set_settings(client: Client, config: dict) -> None:
    if "locale" in config:
        client.set_locale(config["locale"])
    if "country" in config:
        client.set_country(config["country"])
    if "country_code" in config:
        client.set_country_code(config["country_code"])
    if "timezone_offset" in config:
        client.set_timezone_offset(config["timezone_offset"])
    if "device" in config:
        client.set_device(config["device"])
    if "user_agent" in config:
        client.set_user_agent(config["user_agent"])
    if "proxy" in config:
        client.set_proxy(config["proxy"])



def main():
    with open(sys.argv[1], "rb") as conf:
        config = tomllib.load(conf)

    username, password = (
        config["ig_account"]["username"],
        config["ig_account"]["password"],
    )
    session_file = (
        Path("/var/lib/ig-story-fetcher/session.json")
        if "session_file" not in config
        else Path(config["session_file"])
    )
    user_id = config["ig_user_id"]

    client = Client()

    # Get and set settings from config
    set_settings(client, config["instagrapi_settings"])

    login_user(client, username, password, session_file)

    # Make one video out of all of the day's stories
    stories = client.user_stories(user_id=user_id)
    yesterday = date.today() - timedelta(days=1)
    video_filename = f"{yesterday}.mp4"
    with TemporaryDirectory() as stories_dir:
        for story in stories:
            client.story_download(
                story.pk,
                filename=story.taken_at.strftime("%Y%m%d%H%M%S%f"),
                folder=stories_dir,
            )

        video_fullpath = f"{stories_dir}/{video_filename}"
        concatenate_stories(stories_dir, video_fullpath)

        # Send the final video to an s3 bucket
        s3 = boto3.client(
            "s3",
            region_name=config["s3"]["region_name"],
            endpoint_url=config["s3"]["endpoint_url"],
            aws_access_key_id=config["s3"]["access_key_id"],
            aws_secret_access_key=config["s3"]["secret_access_key"],
            config=Config(signature_version="s3v4"),
        )
        bucket_name = config["s3"]["bucket_name"]
        key = f"{config['s3']['bucket_folder']}/{video_filename}"
        with open(video_fullpath, "rb") as video:
            s3.put_object(
                Body=video,
                Bucket=bucket_name,
                Key=key,
                ACL="private",
                CacheControl="max-age=31556926",  # 1 year
            )

    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket_name, "Key": key}, ExpiresIn=86400
    )

    from_address = config["email"]["from_address"]
    to_addresses = ", ".join(config["email"]["mailing_list"])
    message = MIMEMultipart("alternative")
    message["Subject"] = "Stories of the day"
    message["From"] = f"Instagram Stories <{from_address}>"
    message["To"] = to_addresses

    # Create the plain-text and HTML version of your message
    email_text = f"Stories of {yesterday:%d, %b %Y}"
    text = email_text + f": {url}"
    html = f"""\
    <html>
      <body>
         <p>{email_text}</p>
         <a href="{url}">
           <img width="150" height="150"
               src="https://cdn.pixabay.com/photo/2017/11/10/05/34/play-2935460_960_720.png"
           />
         </a>
      </body>
    </html>
    """
    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))

    # Send an email to all configured emails
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        config["smtp"]["host"], config["smtp"]["port"], context=context
    ) as server:
        server.login(config["smtp"]["username"], config["smtp"]["password"])
        server.sendmail(
            from_address, config["email"]["mailing_list"], message.as_string()
        )


if __name__ == "__main__":
    main()

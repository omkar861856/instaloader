import os
import asyncio
from aiograpi import Client
from dotenv import load_dotenv

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

class InstagramService:
    def __init__(self):
        self.cl = Client()
        self.logged_in = False

    async def login(self):
        if not self.logged_in and IG_USERNAME and IG_PASSWORD:
            try:
                await self.cl.login(IG_USERNAME, IG_PASSWORD)
                self.logged_in = True
                print(f"Logged in to Instagram as {IG_USERNAME}")
            except Exception as e:
                print(f"Instagram Login Failed: {e}")
                self.logged_in = False
        return self.logged_in

    async def get_user_info(self, username):
        await self.login()
        try:
            return await self.cl.user_info_by_username(username)
        except Exception as e:
            print(f"Error fetching user info for {username}: {e}")
            return None

    async def get_user_medias(self, username, amount=20):
        await self.login()
        try:
            user_id = await self.cl.user_id_from_username(username)
            return await self.cl.user_medias(user_id, amount)
        except Exception as e:
            print(f"Error fetching medias for {username}: {e}")
            return []

    async def download_media(self, media_url, folder="downloads"):
        await self.login()
        try:
            media_pk = await self.cl.media_pk_from_url(media_url)
            media_info = await self.cl.media_info(media_pk)
            
            if not os.path.exists(folder):
                os.makedirs(folder)
                
            if media_info.media_type == 1: # Photo
                return await self.cl.photo_download(media_pk, folder)
            elif media_info.media_type == 2: # Video
                return await self.cl.video_download(media_pk, folder)
            elif media_info.media_type == 8: # Album
                return await self.cl.album_download(media_pk, folder)
            return None
        except Exception as e:
            print(f"Error downloading media {media_url}: {e}")
            return None

ig_service = InstagramService()

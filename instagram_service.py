import os
import asyncio
try:
    from instaloader import Instaloader, Profile, Post
except ImportError as e:
    import instaloader
    raise ImportError(f"Instaloader components not found in {getattr(instaloader, '__file__', 'unknown')}. Error: {e}")
from dotenv import load_dotenv

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

class InstagramService:
    def __init__(self):
        self.L = Instaloader()
        self.logged_in = False
        
    async def login(self):
        if not self.logged_in and IG_USERNAME and IG_PASSWORD:
            try:
                # Run synchronous login in a thread
                await asyncio.to_thread(self.L.login, IG_USERNAME, IG_PASSWORD)
                self.logged_in = True
                print(f"Logged in to Instagram as {IG_USERNAME}")
            except Exception as e:
                print(f"Instagram Login Failed: {e}")
                self.logged_in = False
        return self.logged_in

    async def get_user_info(self, username):
        await self.login()
        try:
            profile = await asyncio.to_thread(Profile.from_username, self.L.context, username)
            return {
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "profile_pic_url": profile.profile_pic_url,
                "follower_count": profile.followers,
                "following_count": profile.followees,
                "media_count": profile.mediacount,
                "is_private": profile.is_private
            }
        except Exception as e:
            print(f"Error fetching user info for {username}: {e}")
            return None

    async def get_user_medias(self, username, amount=10):
        await self.login()
        try:
            profile = await asyncio.to_thread(Profile.from_username, self.L.context, username)
            medias = []
            count = 0
            for post in profile.get_posts():
                if count >= amount:
                    break
                medias.append({
                    "shortcode": post.shortcode,
                    "url": post.url,
                    "caption": post.caption,
                    "timestamp": post.date_local.isoformat(),
                    "is_video": post.is_video
                })
                count += 1
            return medias
        except Exception as e:
            print(f"Error fetching medias for {username}: {e}")
            return []

    async def download_media(self, media_url_or_shortcode, folder="downloads"):
        await self.login()
        try:
            # Extract shortcode if it's a URL
            shortcode = media_url_or_shortcode
            if "instagram.com/p/" in media_url_or_shortcode:
                shortcode = media_url_or_shortcode.split("/p/")[1].split("/")[0]
            elif "instagram.com/reel/" in media_url_or_shortcode:
                shortcode = media_url_or_shortcode.split("/reel/")[1].split("/")[0]

            post = await asyncio.to_thread(Post.from_shortcode, self.L.context, shortcode)
            
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            # Instaloader downloads to a directory with the post shortcode/owner
            target = os.path.join(folder, shortcode)
            await asyncio.to_thread(self.L.download_post, post, target=target)
            
            return target
        except Exception as e:
            print(f"Error downloading media {media_url_or_shortcode}: {e}")
            return None

ig_service = InstagramService()

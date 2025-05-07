from diffusers.pipelines.pipeline_utils import DiffusionPipeline
from utils.config import MODEL_PATH, is_in_allowed_channel
from discord.ext import commands
import discord
import asyncio
import torch
import time
import io

class Generate(commands.Cog):
    def __init__(self, bot, model_path, generate_lock):
        self.bot = bot
        self.pipe = DiffusionPipeline.from_pretrained(model_path, torch_dtype=torch.float16)
        self.pipe.to("cuda")
        self.pipe.safety_checker = None
        self.generate_lock = generate_lock

    @commands.command()
    @is_in_allowed_channel()
    async def generate(self, ctx, *, prompt: str):
        """Generate an image using the Stable Diffusion model."""
        if not self.generate_lock.locked():
            async with self.generate_lock:
                start_time = time.time()

                status_message = await ctx.send(f"Generating an image for: `{prompt}`. Please wait...")

                try:
                    # Generate the image
                    image = self.pipe(prompt).images[0]  # pyright: ignore

                    elapsed_time = time.time() - start_time
                    await status_message.edit(content=f"Image generated in {elapsed_time:.2f} seconds!")

                    # Save the image to a BytesIO object
                    image_bytes = io.BytesIO()
                    image.save(image_bytes, format="PNG")
                    image_bytes.seek(0)

                    # Send the image to Discord
                    await ctx.send(file=discord.File(fp=image_bytes, filename="generated_image.png"))

                except Exception as e:
                    print(f"[ERROR] {e}")
                    await ctx.send(f"An error occurred: {e}")
        else:
            await ctx.send("A generation is already in progress. Please wait for it to finish.")

async def setup(bot):
    generate_lock = asyncio.Lock()
    await bot.add_cog(Generate(bot, MODEL_PATH, generate_lock))

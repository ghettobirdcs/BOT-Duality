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

                # Send an initial status message
                status_message = await ctx.send(f"Generating an image for: `{prompt}`\n[░░░░░░░░░░]")

                image_ready = asyncio.Event()
                # Simulated back-and-forth loading bar
                async def update_loading_bar():
                    bar_length = 10
                    position = 0
                    direction = 1  # 1 for forward, -1 for backward

                    while not image_ready.is_set():
                        # Create the loading bar with a moving "cursor"
                        bar = ["░"] * bar_length
                        bar[position] = "█"
                        bar_str = "".join(bar)

                        # Update the Discord message
                        await status_message.edit(content=f"Generating an image for: `{prompt}`\n[{bar_str}]")

                        # Update the position of the "cursor"
                        position += direction
                        if position == bar_length - 1:  # Reached the end
                            direction = -1  # Reverse direction
                        elif position == 0:  # Reached the start
                            direction = 1  # Reverse direction

                        await asyncio.sleep(0.2)  # Adjust speed of animation

                    # Smoothly fill the bar when the image is ready
                    for i in range(1, bar_length + 1):
                        bar = ["█"] * i + ["░"] * (bar_length - i)
                        bar_str = "".join(bar)
                        await status_message.edit(content=f"Generating an image for: `{prompt}`\n[{bar_str}]")
                        await asyncio.sleep(0.1)  # Smooth fill animation

                # Run the loading bar in the background
                loading_task = asyncio.create_task(update_loading_bar())

                try:
                    # Run the image generation in a separate thread
                    image = await asyncio.to_thread(
                        lambda: self.pipe(prompt)  # pyright: ignore
                    )

                    # Signal that the image is ready
                    image_ready.set()

                    # Wait for the loading bar to finish filling
                    await loading_task

                    elapsed_time = time.time() - start_time
                    await status_message.edit(content=f"`{prompt}` generated in {elapsed_time:.2f} seconds!")

                    # Save the image to a BytesIO object
                    image_bytes = io.BytesIO()
                    image.images[0].save(image_bytes, format="PNG")
                    image_bytes.seek(0)

                    # Send the image to Discord
                    await ctx.send(file=discord.File(fp=image_bytes, filename="generated_image.png"))

                except Exception as e:
                    print(f"[ERROR] {e}")
                    await status_message.edit(content=f"❌ An error occurred: {e}")
                    image_ready.set()  # Stop the progress bar task
                    try:
                        await loading_task
                    except asyncio.CancelledError:
                        pass
        else:
            await ctx.send("A generation is already in progress. Please wait for it to finish.")

async def setup(bot):
    generate_lock = asyncio.Lock()
    await bot.add_cog(Generate(bot, MODEL_PATH, generate_lock))

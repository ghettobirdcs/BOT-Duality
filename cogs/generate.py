from utils.config import MODEL_PATH, HF_TOKEN, is_in_allowed_channel
from diffusers.pipelines.pipeline_utils import DiffusionPipeline
# from huggingface_hub.utils import logging as hf_logging
from safetensors.torch import save_file
from huggingface_hub import login
from discord.ext import commands
import discord
import asyncio
import torch
import time
import io
import os

# Login to huggingface cli
login(token=HF_TOKEN)

# Enable debug logging
# hf_logging.set_verbosity_debug()

class Generate(commands.Cog):
    def __init__(self, bot, generate_lock):
        self.bot = bot
        self.generate_lock = generate_lock
        self.command_enabled = False

        # Convert .bin files to .safetensors if necessary
        self.convert_bin_to_safetensors()

        self.pipe = DiffusionPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.float16)
        self.pipe.to("cuda")
        # Disable safety checker
        self.pipe.safety_checker = None

    def convert_bin_to_safetensors(self):
        components = ["unet", "vae"]
        for component in components:
            component_path = os.path.join(str(MODEL_PATH), component)
            bin_file = os.path.join(component_path, "diffusion_pytorch_model.bin")
            safetensors_file = os.path.join(component_path, "diffusion_pytorch_model.safetensors")

            # If .bin file exists and not .safetensors
            if os.path.exists(bin_file) and not os.path.exists(safetensors_file):
                print(f"Converting {bin_file} to {safetensors_file}...")
                # Load the .bin file
                state_dict = torch.load(bin_file, map_location="cpu")
                # Save as .safetensors
                save_file(state_dict, safetensors_file)
                print(f"Converted {bin_file} to {safetensors_file}!")

    @commands.command()
    @is_in_allowed_channel()
    async def generate(self, ctx, *, prompt: str):
        if not self.command_enabled:
            await ctx.send("The command is currently disabled by the bot's father. Please try again later.")
            return

        if not self.generate_lock.locked():
            async with self.generate_lock:
                start_time = time.time()

                # Send an initial status message
                print(f"Generating: {prompt}...")
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
                    image = await asyncio.to_thread(lambda: self.pipe(prompt))  # pyright: ignore

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
            # TODO: Handle the case where the command is already in progress
            await ctx.send("Something went wrong. Please try again later.")

    @commands.command()
    async def clear_messages(self, ctx):
        # Clear message history in the channel
        async for message in ctx.channel.history(limit=10):
            try:
                await message.delete()
            except discord.Forbidden:
                pass

    @commands.command()
    @commands.is_owner()
    async def toggle_gen(self, ctx):
        """Toggle the generate command on or off."""
        self.command_enabled = not self.command_enabled
        status = "enabled" if self.command_enabled else "disabled"
        await ctx.send(f"The generate command has been {status}.")

async def setup(bot):
    generate_lock = asyncio.Lock()
    await bot.add_cog(Generate(bot, generate_lock))

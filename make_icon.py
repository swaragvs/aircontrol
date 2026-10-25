from PIL import Image, ImageDraw

image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 240, 240), 56, fill=(245, 185, 66, 255))
draw.ellipse((96, 80, 160, 144), fill=(28, 37, 48, 255))
image.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

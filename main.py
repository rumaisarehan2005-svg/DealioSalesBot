import discord
from discord.ext import commands
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============ API KEYS ============
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# Check if tokens exist
if not DISCORD_TOKEN:
    print("❌ ERROR: Please add your DISCORD_TOKEN in .env file")
    exit()

if not HUGGINGFACE_TOKEN:
    print("⚠️ WARNING: HUGGINGFACE_TOKEN not found. AI features will use fallback responses.")
    print("   Get free token from: https://huggingface.co/settings/tokens")
else:
    print("🤖 Hugging Face AI is ACTIVE")

# Load product database
with open('products.json', 'r', encoding='utf-8') as f:
    PRODUCTS = json.load(f)

# Load orders function
def load_orders():
    if os.path.exists('orders.json'):
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Save order function
def save_order(order):
    orders = load_orders()
    orders.append(order)
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

# AI Sales Prompt
SALES_SYSTEM_PROMPT = """You are Dealio, a friendly and professional sales assistant for Twitch streamers. You sell avatars, overlays, emotes, and streaming assets.

IMPORTANT RULES:
1. Keep responses VERY SHORT - maximum 2 sentences
2. Be enthusiastic and helpful
3. Suggest products based on what the streamer needs
4. If someone asks about price, tell them to type !products
5. If someone wants to buy, tell them to type !buy [category] [product]
6. Never ask for personal information
7. Be positive and encouraging

Streamer's question: """

# Hugging Face API function
async def get_ai_response(question):
    if not HUGGINGFACE_TOKEN:
        import random
        fallback_responses = [
            "Thanks for asking! Check out our products with `!products` or `!shop` to see what we offer! 🎨",
            "Great question! For pricing, please use `!products` to see our full catalog with prices! 💰",
            "I'd love to help! Could you type `!category avatars` or `!category overlays` to see specific products? 🛒",
            "That's a great question for a Twitch streamer! We have many options. Try `!shop` to browse everything! ✨",
            "Thanks for your interest in Dealio! Type `!help_shop` to see all commands or `!products` to see what we sell! 🚀"
        ]
        return random.choice(fallback_responses)

    try:
        API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3.1-8B-Instruct"
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": f"{SALES_SYSTEM_PROMPT}\n\n{question}\n\nDealio's response:",
            "parameters": {
                "max_new_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True
            }
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                reply = result[0].get('generated_text', str(result[0]))
            elif isinstance(result, dict) and 'generated_text' in result:
                reply = result['generated_text']
            else:
                reply = str(result)

            reply = reply.replace(SALES_SYSTEM_PROMPT, "")
            reply = reply.replace(question, "")
            reply = reply.replace("Dealio's response:", "")
            reply = reply.strip()

            if len(reply) > 500:
                reply = reply[:500] + "..."

            if reply:
                return reply
            else:
                return "Thanks for asking! Check out `!products` to see our catalog or `!help_shop` for all commands! 🎨"
        else:
            print(f"Hugging Face API Error: {response.status_code}")
            return "I'm having trouble thinking right now! Please try `!products` to see what we sell. 🛒"

    except requests.exceptions.Timeout:
        return "Sorry, I'm thinking slowly today! Try `!products` to see our catalog directly. 📦"
    except Exception as e:
        print(f"AI Error: {e}")
        return "Dealio is ready to help! Type `!products` to see our Twitch assets or `!help_shop` for all commands! ✨"

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store shopping carts
shopping_carts = {}

class ShoppingCart:
    def __init__(self, user_id):
        self.user_id = user_id
        self.items = []
        self.total = 0

    def add_item(self, category_key, product_key):
        product = PRODUCTS['categories'][category_key]['products'][product_key]
        self.items.append({
            'category': category_key,
            'product_key': product_key,
            'name': product['name'],
            'price': product['price'],
            'delivery_time': product['delivery_time']
        })
        self.total += product['price']
        return product['name'], product['price']

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            item = self.items.pop(index)
            self.total -= item['price']
            return item['name']
        return None

    def clear(self):
        self.items = []
        self.total = 0

@bot.event
async def on_ready():
    print(f'✅ Dealio is online as {bot.user}')
    total_products = sum(len(cat['products']) for cat in PRODUCTS['categories'].values())
    print(f'📦 Selling {total_products} Twitch streaming products')
    await bot.change_presence(activity=discord.Game(name="!shop | !ask | Twitch Assets"))

# ============ AI CHAT COMMAND ============

@bot.command(name='ask')
async def ask_dealio(ctx, *, question: str = None):
    """Ask Dealio AI anything about streaming assets"""
    if not question:
        await ctx.send("❓ Ask me something! Examples:\n`!ask What overlay is best?`\n`!ask How much are emotes?`\n`!ask Do you do custom work?`")
        return

    async with ctx.typing():
        response = await get_ai_response(question)
        await ctx.send(f"🛒 **Dealio:** {response}")

# ============ SHOP COMMANDS ============

@bot.command(name='shop')
async def show_shop(ctx):
    """Show all product categories"""
    embed = discord.Embed(
        title="🛒 Dealio - Twitch Streamer Shop",
        description="Everything you need to level up your stream!",
        color=0x9146FF
    )
    for cat_key, category in PRODUCTS['categories'].items():
        product_count = len(category['products'])
        embed.add_field(
            name=f"{category['name']}",
            value=f"*{category['description']}*\n📦 {product_count} products\n➡️ `!category {cat_key}`",
            inline=False
        )
    embed.set_footer(text="Use !help_shop for all commands | !ask for AI help")
    await ctx.send(embed=embed)

@bot.command(name='category')
async def show_category(ctx, category_key: str = None):
    """Show products in a category"""
    if not category_key:
        await ctx.send("❌ Please specify a category. Use `!shop` to see categories.")
        return
    if category_key not in PRODUCTS['categories']:
        await ctx.send(f"❌ Category '{category_key}' not found. Use `!shop` to see categories.")
        return

    category = PRODUCTS['categories'][category_key]
    embed = discord.Embed(title=f"{category['name']}", description=category['description'], color=0x9146FF)
    for prod_key, product in category['products'].items():
        embed.add_field(
            name=f"**{product['name']}** - ${product['price']}",
            value=f"📝 {product['description']}\n⏱️ Delivery: {product['delivery_time']}\n➡️ `!buy {category_key} {prod_key}`",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name='products')
async def list_products(ctx):
    """Quick list of all products with prices"""
    embed = discord.Embed(
        title="📦 All Products & Prices",
        description="Type `!category [name]` for details, `!buy [category] [product]` to purchase",
        color=0x9146FF
    )
    for cat_key, category in PRODUCTS['categories'].items():
        product_list = ""
        for prod_key, product in category['products'].items():
            product_list += f"• {product['name']} - **${product['price']}**\n"
        embed.add_field(name=category['name'], value=product_list, inline=True)
    await ctx.send(embed=embed)

@bot.command(name='buy')
async def add_to_cart(ctx, category_key: str = None, product_key: str = None):
    """Add product to cart: !buy avatars png_basic"""
    if not category_key or not product_key:
        await ctx.send("❌ Usage: `!buy [category] [product]`\nExample: `!buy avatars png_basic`\nUse `!products` to see all products.")
        return
    if category_key not in PRODUCTS['categories']:
        await ctx.send(f"❌ Category '{category_key}' not found. Use `!shop` to see categories.")
        return
    if product_key not in PRODUCTS['categories'][category_key]['products']:
        await ctx.send(f"❌ Product not found. Use `!category {category_key}` to see products.")
        return

    if ctx.author.id not in shopping_carts:
        shopping_carts[ctx.author.id] = ShoppingCart(ctx.author.id)

    cart = shopping_carts[ctx.author.id]
    product_name, price = cart.add_item(category_key, product_key)

    embed = discord.Embed(title="✅ Added to Cart!", description=f"**{product_name}** - **${price}** has been added to your cart.", color=0x00FF00)
    embed.add_field(name="Cart Total", value=f"💰 ${cart.total}", inline=False)
    embed.add_field(name="Next Steps", value="Type `!cart` to view cart\nType `!checkout` to complete purchase", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='cart')
async def view_cart(ctx):
    """View your shopping cart"""
    if ctx.author.id not in shopping_carts or not shopping_carts[ctx.author.id].items:
        await ctx.send("🛒 Your cart is empty. Use `!shop` to browse products!")
        return

    cart = shopping_carts[ctx.author.id]
    embed = discord.Embed(title="🛒 Your Shopping Cart", color=0x9146FF)
    items_text = ""
    for i, item in enumerate(cart.items):
        items_text += f"`{i+1}.` **{item['name']}** - ${item['price']}\n"
    embed.add_field(name="Items:", value=items_text, inline=False)
    embed.add_field(name="Total", value=f"💰 **${cart.total}**", inline=False)
    embed.add_field(name="Commands", value="`!remove [number]` - Remove item\n`!checkout` - Complete purchase\n`!clearcart` - Clear cart", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='remove')
async def remove_item(ctx, item_number: int = None):
    """Remove item from cart: !remove 1"""
    if ctx.author.id not in shopping_carts or not shopping_carts[ctx.author.id].items:
        await ctx.send("🛒 Your cart is empty!")
        return
    if not item_number:
        await ctx.send("❌ Usage: `!remove [item_number]`\nUse `!cart` to see item numbers.")
        return

    cart = shopping_carts[ctx.author.id]
    item_name = cart.remove_item(item_number - 1)
    if item_name:
        await ctx.send(f"✅ Removed **{item_name}** from your cart. New total: **${cart.total}**")
    else:
        await ctx.send("❌ Invalid item number. Use `!cart` to see your items.")

@bot.command(name='clearcart')
async def clear_cart(ctx):
    """Clear your entire shopping cart"""
    if ctx.author.id in shopping_carts:
        shopping_carts[ctx.author.id].clear()
        await ctx.send("🗑️ Your cart has been cleared!")
    else:
        await ctx.send("🛒 Your cart is already empty!")

@bot.command(name='checkout')
async def checkout(ctx):
    """Proceed to checkout"""
    if ctx.author.id not in shopping_carts or not shopping_carts[ctx.author.id].items:
        await ctx.send("🛒 Your cart is empty. Add items with `!buy` first!")
        return

    cart = shopping_carts[ctx.author.id]
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ctx.author.id}"

    embed = discord.Embed(title="📋 Order Summary", description=f"**Order ID:** `{order_id}`", color=0xFFA500)
    items_text = ""
    for item in cart.items:
        items_text += f"• {item['name']} - ${item['price']}\n"
    embed.add_field(name="Items:", value=items_text, inline=False)
    embed.add_field(name="Total Amount", value=f"💰 **${cart.total} USD**", inline=False)
    embed.add_field(
        name="How to Pay",
        value=f"""**Payment Options:**
1. 💳 **PayPal:** dealio@yourbusiness.com
2. 💎 **Crypto:** Contact for wallet address

**To complete your order:**
• Send payment to the above address
• Type `!confirm_payment {order_id}`

**Important:** Order processed after payment confirmation!""",
        inline=False
    )

    order = {
        'order_id': order_id,
        'user_id': ctx.author.id,
        'user_name': str(ctx.author),
        'items': cart.items.copy(),
        'total': cart.total,
        'status': 'pending_payment',
        'created_at': datetime.now().isoformat()
    }
    save_order(order)
    cart.order_id = order_id

    await ctx.send(embed=embed)

    try:
        dm_embed = discord.Embed(title="💳 Payment Instructions - Dealio", description=f"**Order #{order_id}**", color=0x00FF00)
        dm_embed.add_field(name="Total Due", value=f"${cart.total} USD", inline=True)
        dm_embed.add_field(name="PayPal", value="dealio@yourbusiness.com", inline=True)
        dm_embed.add_field(name="Reference", value=f"Use Order ID: {order_id}", inline=False)
        dm_embed.add_field(name="After Payment", value=f"Type `!confirm_payment {order_id}` in the server", inline=False)
        await ctx.author.send(embed=dm_embed)
        await ctx.send("📧 **Check your DMs!** I've sent you payment instructions.")
    except discord.Forbidden:
        await ctx.send("⚠️ I couldn't DM you. Please enable DMs from server members.")

@bot.command(name='confirm_payment')
async def confirm_payment(ctx, order_id: str = None):
    """Confirm payment: !confirm_payment ORD-..."""
    if not order_id:
        await ctx.send("❌ Usage: `!confirm_payment [order_id]`")
        return

    orders = load_orders()
    order_found = None
    order_index = -1

    for i, order in enumerate(orders):
        if order['order_id'] == order_id and order['user_id'] == ctx.author.id:
            order_found = order
            order_index = i
            break

    if not order_found:
        await ctx.send("❌ Order not found. Please check your Order ID.")
        return
    if order_found['status'] != 'pending_payment':
        await ctx.send(f"⚠️ This order is already {order_found['status']}.")
        return

    orders[order_index]['status'] = 'payment_received'
    orders[order_index]['payment_confirmed_at'] = datetime.now().isoformat()

    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

    await ctx.send(f"✅ Payment confirmed for order `{order_id}`! A staff member will deliver your items soon. Thank you! 🎉")

# ============ INFO COMMANDS ============

@bot.command(name='price')
async def check_price(ctx, category: str = None, product: str = None):
    """Check price: !price avatars png_basic"""
    if not category or not product:
        await ctx.send("❌ Usage: `!price [category] [product]`\nUse `!products` to see all products.")
        return
    try:
        product_data = PRODUCTS['categories'][category]['products'][product]
        embed = discord.Embed(title=f"💰 Price: {product_data['name']}", description=f"**${product_data['price']}** USD", color=0x00FF00)
        embed.add_field(name="Delivery Time", value=product_data['delivery_time'], inline=True)
        embed.add_field(name="Purchase", value=f"`!buy {category} {product}`", inline=True)
        await ctx.send(embed=embed)
    except KeyError:
        await ctx.send("❌ Product not found. Use `!products` to see all products.")

@bot.command(name='preview')
async def preview_item(ctx, category: str = None, product: str = None):
    """Preview a product: !preview avatars png_basic"""
    if not category or not product:
        await ctx.send("❌ Usage: `!preview [category] [product]`")
        return
    try:
        product_data = PRODUCTS['categories'][category]['products'][product]
        embed = discord.Embed(title=f"🖼️ Preview: {product_data['name']}", description=product_data['description'], color=0x9146FF)
        embed.add_field(name="Price", value=f"${product_data['price']}", inline=True)
        embed.add_field(name="Delivery Time", value=product_data['delivery_time'], inline=True)
        embed.add_field(name="Purchase", value=f"`!buy {category} {product}`", inline=False)
        await ctx.send(embed=embed)
    except KeyError:
        await ctx.send("❌ Product not found. Use `!category [name]` to see available products.")

@bot.command(name='portfolio')
async def show_portfolio(ctx):
    """Show examples of previous work"""
    embed = discord.Embed(title="🎨 Dealio Portfolio", description="Check out our previous work!", color=0x9146FF)
    embed.add_field(
        name="View Examples",
        value="• **Avatars:** Contact us for portfolio\n• **Overlays:** Contact us for samples\n• **Emotes:** Contact us for examples\n\n**Custom Work:** Contact Dealio staff for a custom quote!\n**Ask AI:** Type `!ask What custom work can you do?`",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='support')
async def support_ticket(ctx):
    """Create a support ticket"""
    embed = discord.Embed(title="🎫 Dealio Support", description="How can we help you?", color=0xFFA500)
    embed.add_field(
        name="Contact Us",
        value="For support, please DM a staff member or email support@dealio.com\n\n**Common Issues:**\n• Order not received → Contact with Order ID\n• Custom commission → Describe what you need\n• Refund request → Provide Order ID and reason\n• Product questions → Type `!ask [your question]`",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name='deals')
async def deals(ctx):
    """Show current deals"""
    embed = discord.Embed(title="🔥 Current Deals from Dealio!", description="Limited time offers!", color=0xFF4500)
    embed.add_field(name="Bundle Deal", value="Buy any **Overlay Pack + Emote Pack** and get **10% OFF**! Use code: `STREAMER10`", inline=False)
    embed.add_field(name="First Purchase", value="First-time buyers get **15% OFF**! Use code: `FIRSTDEAL15`", inline=False)
    embed.add_field(name="Referral", value="Refer another streamer and both get **$5 OFF** your next order!", inline=False)
    embed.add_field(name="Ask AI", value="Not sure what to buy? Type `!ask What should I buy for my stream?`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='help_shop')
async def help_shop(ctx):
    """Show all commands"""
    embed = discord.Embed(title="📚 Dealio - All Commands", description="Your Twitch streaming asset store!", color=0x9146FF)
    embed.add_field(name="🤖 AI Chat", value="`!ask [question]` - Ask Dealio anything", inline=False)
    embed.add_field(
        name="🛒 Shopping",
        value="`!shop` - Browse categories\n`!category [name]` - View products\n`!products` - List all products\n`!price [category] [product]` - Check price\n`!buy [category] [product]` - Add to cart\n`!cart` - View cart\n`!remove [number]` - Remove item\n`!clearcart` - Clear cart\n`!checkout` - Complete purchase",
        inline=False
    )
    embed.add_field(
        name="🎨 Info",
        value="`!preview [category] [product]` - Preview product\n`!portfolio` - See examples\n`!deals` - Current discounts\n`!support` - Get help",
        inline=False
    )
    embed.add_field(name="💰 Payment", value="`!confirm_payment [order_id]` - Confirm payment", inline=False)
    await ctx.send(embed=embed)

# ============ RUN BOT ============
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your .env file.")
    except Exception as e:
        print(f"❌ Error: {e}")
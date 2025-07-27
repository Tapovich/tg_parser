import os
from dotenv import load_dotenv

load_dotenv()

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
    CHANNEL_ID = os.getenv('CHANNEL_ID')  # ID канала для публикации (@channel или -100123456789)
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Telethon настройки
    API_ID = int(os.getenv('API_ID', 0))
    API_HASH = os.getenv('API_HASH')
    PHONE_NUMBER = os.getenv('PHONE_NUMBER')
    
    # RSS источники
    RSS_SOURCES = [                 # Дуров через Nitter
    ]
    
    # Telegram каналы для мониторинга
    TG_CHANNELS = [
        # Официальные каналы
        '@durov',                    # Личный канал Павла Дурова
        '@telegram',                 # Официальные новости Telegram
        '@toncoin',                  # Официальный канал TON Foundation
        
        # Новостные каналы
        '@tginfo',                   # Все обновления, фичи, бета-версии Telegram
        '@cryptotonhunter',          # Быстрые новости и инсайды по TON, Gifts, ботам
        '@ton_society',              # Гранты, инициативы, экосистема
        '@ton_blockchain',           # Новости TON и разработчиков
        '@tonstatus',                # Обновления сети, статы, события
        
        # Аналитические каналы
        '@Exploitex',                # Расследования, авторский разбор
        '@the_club_100',             # Постоянные посты с мнением и цифрами
        '@cryptover1',               # Хайп + аналитика по TON и Telegram-экономике
        
        # Специализированные каналы
        '@toncaps',                  # Сливы, твиттер-переводы, разгоны мемкойнов
        '@tap2earn_ru',              # Новости из play-to-earn мира TON
        '@tonnft',                   # NFT-сегмент TON: анонсы, дропы
        '@gifts_ru',                 # Новости по Telegram Gifts, механики, баги
        
        # Дополнительные каналы
        '@crypta',                   # 450$
        '@fuckbroton',
        '@xh_room',
        '@felon_',
        '@projectxvip',
        '@tontopic_1',               # 300$
        '@vanbaypromo',              # 500$
        '@evgenahata',               # 300$
        '@lovebanknote',             # реф
        '@agentadurovatg',           # реф
        '@ton_vseznayka',
        '@telelakel',
        '@tonlow',
        '@Pepes_Gold',
        '@ne_investor',
        '@PodarokDurova',
        '@gift_hater'
    ]
    
    # Ключевые слова для фильтрации
    KEYWORDS = [
        # --- ENGLISH: TON / Telegram Core ---
        "TON", "Ton", "ton",
        "TONCOIN", "Toncoin", "toncoin",
        "TELEGRAM", "Telegram", "telegram",
        
        # --- Gifts / Stars / Premium ---
        "GIFTS", "Gifts", "gifts",
        "STARS", "Stars", "stars",
        "PREMIUM", "Premium", "premium",
        "TG PREMIUM", "Tg Premium", "tg premium",

        # --- Features / Bots / Updates ---
        "BOT", "Bot", "bot",
        "BOTS", "Bots", "bots",
        "UPDATE", "Update", "update",
        "UPDATES", "Updates", "updates",
        "FEATURE", "Feature", "feature",
        "FEATURES", "Features", "features",

        # --- Crypto-specific ---
        "AIRDROP", "Airdrop", "airdrop",
        "TOKEN", "Token", "token",
        "TOKENS", "Tokens", "tokens",
        "CRYPTO", "Crypto", "crypto",
        "BLOCKCHAIN", "Blockchain", "blockchain",
        "WEB3", "Web3", "web3",
        "DEFI", "DeFi", "defi",
        "NFT", "Nft", "nft",
        "DROP", "Drop", "drop",
        "LAUNCH", "Launch", "launch",
        "IDO", "Ido", "ido",
        "DEX", "Dex", "dex",
        "WALLET", "Wallet", "wallet",

        # --- RUSSIAN: TON / Telegram / Gifts / Stars ---
        "ТЕЛЕГРАМ", "Телеграм", "телеграм",
        "ТОН", "Тон", "тон",
        "ТОНКОИН", "Тонкоин", "тонкоин",

        "ПОДАРОК", "Подарок", "подарок",
        "ПОДАРКИ", "Подарки", "подарки",
        "СТАРСЫ", "Старсы", "старсы",
        "ЗВЕЗДЫ", "Звезды", "звезды",
        "ПРЕМИУМ", "Премиум", "премиум",

        # --- RUS: Crypto / Tech ---
        "КРИПТА", "Крипта", "крипта",
        "КРИПТОВАЛЮТА", "Криптовалюта", "криптовалюта",
        "БЛОКЧЕЙН", "Блокчейн", "блокчейн",
        "ВЕБ3", "Веб3", "веб3",
        "ДЕФИ", "Дефи", "дефи",
        "НФТ", "нфт",

        # --- RUS: Activity / Actions ---
        "РАЗДАЧА", "Раздача", "раздача",
        "ЭЙРДРОП", "Эйрдроп", "эйрдроп",
        "ОБНОВЛЕНИЕ", "Обновление", "обновление",
        "БОТ", "Бот", "бот",
        "БОТЫ", "Боты", "боты",
        "КАМПАНИЯ", "Кампания", "кампания",
        "ЗАПУСК", "Запуск", "запуск"
    ]
    
    # Настройки мониторинга
    MONITORING_INTERVAL_MINUTES = int(os.getenv('MONITORING_INTERVAL_MINUTES', 5))  # По умолчанию 5 минут
    RSS_CHECK_INTERVAL_MINUTES = int(os.getenv('RSS_CHECK_INTERVAL_MINUTES', 3))    # RSS проверяем чаще
    TG_CHECK_INTERVAL_MINUTES = int(os.getenv('TG_CHECK_INTERVAL_MINUTES', 7))      # Telegram чуть реже
    
    # AI настройки
    AUTO_REWRITE_ENABLED = False  # Отключено - только ручной режим с промптами
    MANUAL_MODE_ONLY = True  # Только ручной режим с советами и промптами
    
    @classmethod
    def validate(cls):
        """Проверяет наличие обязательных переменных"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID не найден в переменных окружения")
        return True
    
    @classmethod
    def validate_channel(cls):
        """Проверяет настройки канала для публикации"""
        if not cls.CHANNEL_ID:
            raise ValueError("CHANNEL_ID не найден в переменных окружения")
        return True
    
    @classmethod
    def validate_telethon(cls):
        """Проверяет настройки Telethon"""
        if not cls.API_ID:
            raise ValueError("API_ID не найден в переменных окружения")
        if not cls.API_HASH:
            raise ValueError("API_HASH не найден в переменных окружения")
        if not cls.PHONE_NUMBER:
            raise ValueError("PHONE_NUMBER не найден в переменных окружения")
        return True

config = Config()

ADMIN_USERS = [config.ADMIN_ID, 6355723723]

def is_admin(user_id):
    return user_id in ADMIN_USERS 
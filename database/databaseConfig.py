import os
from dotenv import find_dotenv, load_dotenv
from pymongo import MongoClient, TEXT
from utils.logger import Logger

logger = Logger.get_logger("databaseConfig")

load_dotenv(find_dotenv())

connectionString = os.environ.get("MONGODB_URI")

# Fallback to local MongoDB if connection string is not properly configured
if (
    not connectionString
    or "username:password" in connectionString
    or connectionString == "mongodb+srv://username:password@cluster.mongodb.net/"
):
    logger.warning(
        "MONGODB_URI not properly configured, using local MongoDB"
    )
    connectionString = "mongodb://localhost:27017/"

try:
    dbclient = MongoClient(connectionString)
    # Test the connection
    dbclient.admin.command("ping")
    logger.info("Successfully connected to MongoDB")
except Exception as e:
    logger.error("Failed to connect to MongoDB", exc_info=True)
    logger.info("Attempting to connect to local MongoDB as fallback...")
    connectionString = "mongodb://localhost:27017/"
    dbclient = MongoClient(connectionString)
    dbclient.admin.command("ping")
    logger.info("Connected to local MongoDB")

beehive = dbclient.beehive
db = beehive

def get_beehive_user_collection():
    return beehive.users


def get_beehive_image_collection():
    return beehive.images


def get_beehive_admin_collection():
    return beehive.admins


def get_beehive_notification_collection():
    return beehive.notifications


def get_beehive_message_collection():
    return beehive.messages


def initialize_text_index():
    try:
        image_collection = get_beehive_image_collection()
        user_collection = get_beehive_user_collection()
        existing_indexes = image_collection.index_information()
        existing_user_indexes = user_collection.index_information()
        
        if 'title_text_description_text' not in existing_indexes:
            image_collection.create_index([
                ('title', TEXT),
                ('description', TEXT)
            ], name='title_text_description_text')
            logger.info("Text index created on image collection")
        else:
            logger.debug("Text index already exists on image collection")
        # Ensure an index exists for OTP verification queries to keep lookups fast
        try:
            otp_collection = beehive.email_otps
            otp_indexes = otp_collection.index_information()
            if 'email_verified_idx' not in otp_indexes:
                otp_collection.create_index(
                    [("email", 1), ("verified", 1), ("verified_at", -1)],
                    name='email_verified_idx',
                )
                logger.info("Created index on email_otps (email, verified, verified_at)")
            else:
                logger.debug("email_verified_idx already exists on email_otps")

            # Add filename and thumbnail_filename indexes
            if 'filename_1' not in existing_indexes:
                image_collection.create_index([('filename', 1)], name='filename_1')
                logger.info("Index created on filename in image collection")
            if 'thumbnail_filename_1' not in existing_indexes:
                image_collection.create_index([('thumbnail_filename', 1)], name='thumbnail_filename_1')
                logger.info("Index created on thumbnail_filename in image collection")
            
            # Add user_id and compound user_id + created_at indexes
            if 'user_id_1' not in existing_indexes:
                image_collection.create_index([('user_id', 1)], name='user_id_1')
                logger.info("Index created on user_id in image collection")
            if 'user_id_1_created_at_-1' not in existing_indexes:
                image_collection.create_index([('user_id', 1), ('created_at', -1)], name='user_id_1_created_at_-1')
                logger.info("Compound index created on user_id and created_at in image collection")

            # Add user collection indexes
            # The username index MUST be unique to prevent race-condition duplicates.
            # If an old non-unique index exists, drop it first so we can recreate
            # it with unique=True.
            if 'username_1' in existing_user_indexes:
                if not existing_user_indexes['username_1'].get('unique'):
                    user_collection.drop_index('username_1')
                    logger.info("Dropped non-unique username_1 index to replace with unique index")
                    user_collection.create_index([('username', 1)], name='username_1', unique=True)
                    logger.info("Unique index created on username in user collection")
                # else: already unique — nothing to do
            else:
                user_collection.create_index([('username', 1)], name='username_1', unique=True)
                logger.info("Unique index created on username in user collection")
            if 'email_1' not in existing_user_indexes:
                user_collection.create_index([('email', 1)], name='email_1')
                logger.info("Index created on email in user collection")
        except Exception as ie:
            logger.error(f"Error creating collection indexes: {ie}")
    except Exception as e:
        logger.error(f"Error creating text index: {str(e)}")

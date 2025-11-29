DB_HOST = "host"
DB_PORT = 5432
DB_NAME = "dbname"
DB_USER = "user"
DB_PASS = "password"

NUM_PRODUCERS = 3
NUM_CONSUMERS = NUM_PRODUCERS
EVENTS_PER_PRODUCER = 5000
DURATION_SECONDS = 60

BOOTSTRAP_SERVERS = 'localhost:9092'
AGGREGATOR_GROUP_ID = 'aggregator-group'

AD_TYPES = ['banner', 'video', 'popup', 'native', 'sponsored', 'interstitial', 'rewarded']
EVENT_TYPES = ['view', 'click', 'purchase']

NUM_CAMPAIGNS = 10
ADS_PER_CAMPAIGN = 100
TOTAL_ADS = NUM_CAMPAIGNS * ADS_PER_CAMPAIGN

TOPIC_NAME = 'events'
PARTITIONS = 3
REPLICATION_FACTOR = 1

EVENTS_TOPIC = 'events'
WATERMARK_TOPIC = 'local-watermarks'
CONSUMER_GROUP_ID = 'postgres-inserter-group'
BATCH_SIZE = EVENTS_PER_PRODUCER // 10

RESULT_TOPIC = 'results'
DISTRIBUTION = 'mmpp' 

const pool = require('../config/pg');
const redis = require('../config/redis');
const { calculatePriceChange } = require('../services/calculatePriceChange');
require("dotenv").config();

let cache = { data: null, timestamp: 0 };
const CACHE_DURATION = 30 * 1000; // cache 30 seconds (giảm từ 60s để real-time hơn)

exports.getTickerBar = async (req, res) => {
  try {
    // 1️⃣ Check memory cache first
    if (cache.data && Date.now() - cache.timestamp < CACHE_DURATION) {
      return res.json(cache.data);
    }

    // 2️⃣ Try Redis cache
    const redisCache = await redis.get('ticker:bar:all').catch(() => null);
    if (redisCache) {
      const parsedCache = JSON.parse(redisCache);
      cache = { data: parsedCache, timestamp: Date.now() };
      return res.json(parsedCache);
    }

    // 3️⃣ Define symbols to display (configurable)
    const displaySymbols = [
      // Crypto (from Binance stream - real-time data)
      'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT',
      
      // US Stocks
      'AAPL', 'MSFT', 'GOOGL', 'TSLA',
      
      // Indices
      '^VNINDEX.VN', '^GSPC', '^DJI', '^IXIC',
      
      // Forex
      'EURUSD=X',
      
      // Commodities
      'GC=F', 'CL=F'
    ];

    // 4️⃣ Get assets from DB
    const { rows: assets } = await pool.query(`
      SELECT id, symbol, name, asset_type, exchange
      FROM assets
      WHERE symbol = ANY($1)
      AND status = 'OK'
    `, [displaySymbols]);

    if (assets.length === 0) {
      console.warn('⚠️  No assets found in database for ticker bar');
      return res.json([]);
    }

    console.log(`📊 Calculating price changes for ${assets.length} assets`);

    // 5️⃣ Calculate price change for each asset (parallel)
    const tickerPromises = assets.map(async (asset) => {
      try {
        const priceData = await calculatePriceChange(
          asset.id,
          asset.symbol,
          asset.asset_type
        );

        if (!priceData) {
          console.warn(`⚠️  No price data for ${asset.symbol} (${asset.asset_type})`);
          return null;
        }

        return {
          symbol: asset.symbol.replace('^', '').replace('=X', '').replace('=F', ''),
          name: asset.name,
          assetType: asset.asset_type,
          exchange: asset.exchange,
          price: parseFloat(priceData.currentPrice.toFixed(2)),
          changePercent: parseFloat(priceData.changePercent.toFixed(2)),
          positive: priceData.positive
        };
      } catch (err) {
        console.error(`❌ Error calculating change for ${asset.symbol}:`, err.message);
        return null;
      }
    });

    const results = await Promise.all(tickerPromises);
    const validTickers = results.filter(Boolean);

    console.log(`✅ Successfully calculated ${validTickers.length}/${assets.length} tickers`);

    // 6️⃣ Cache result (memory + Redis)
    cache = { data: validTickers, timestamp: Date.now() };

    // Cache in Redis for distributed cache
    await redis.setex('ticker:bar:all', 30, JSON.stringify(validTickers)).catch(err => {
      console.error('Redis cache error:', err.message);
    });

    res.json(validTickers);

  } catch (error) {
    console.error("❌ Error fetching ticker data:", error.message);
    console.error(error.stack);
    res.status(500).json({ message: "Error fetching ticker data from database" });
  }
};

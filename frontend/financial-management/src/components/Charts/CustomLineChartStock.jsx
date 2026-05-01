import React, { useState, useEffect } from "react";
import { XAxis, YAxis, ResponsiveContainer, CartesianGrid, Area, AreaChart, Tooltip } from "recharts";
import StockMarket from "../News/StockMarket";
import TitleStock from "../News/TitleStock";
import { addThousandsSeperator } from "../../utils/helper";
import axiosInstance from "../../utils/axiosInstance";
import { API_PATHS } from "../../utils/apiPaths";
import moment from "moment";

const CustomLineChartStock = ({symbol, onAddToWatchlist}) => {
  const [selectedRange, setSelectedRange] = useState('1D');
  const [chartData, setChartData] = useState([]);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Time range mapping
  const TIME_RANGE_LABELS = {
    '1D': '1 NGÀY QUA',
    '5D': '5 NGÀY QUA',
    '1M': '1 THÁNG QUA',
    '3M': '3 THÁNG QUA',
    'YTD': 'ĐẦU NĂM ĐẾN NAY',
    '1Y': '1 NĂM QUA',
    '5Y': '5 NĂM QUA'
  };

  // Calculate start time based on selected range
  const getTimeParams = (range) => {
    const end = new Date();
    let start = new Date();
    let timeframe = '1m';

    switch(range) {
      case '1D':
        timeframe = '1m';
        start.setDate(end.getDate() - 1);
        break;
      case '5D':
        timeframe = '5m';
        start.setDate(end.getDate() - 7);
        break;
      case '1M':
        timeframe = '1d';
        start.setMonth(end.getMonth() - 1);
        break;
      case '3M':
        timeframe = '1d';
        start.setMonth(end.getMonth() - 3);
        break;
      case 'YTD':
        timeframe = '2d';
        start = new Date(end.getFullYear(), 0, 1);
        break;
      case '1Y':
        timeframe = '1d';
        start.setFullYear(end.getFullYear() - 1);
        break;
      case '5Y':
        timeframe = '1d';
        start.setFullYear(end.getFullYear() - 5);
        break;
      default:
        timeframe = '1m';
        start.setDate(end.getDate() - 1);
    }

    return {
      timeframe,
      start: start.toISOString(),
      end: end.toISOString()
    };
  };

  // Fetch summary data from API
  const fetchSummaryData = async () => {
    if (!symbol) return;
    
    try {
      const response = await axiosInstance.get(`${API_PATHS.MARKET.SUMMARY}?symbol=${symbol}`);
      setSummaryData(response.data);
      console.log("Summary data loaded:", response.data);
    } catch (error) {
      console.error("Error fetching summary data:", error);
      setSummaryData(null);
    }
  };

  // Fetch chart data from API
  const fetchChartData = async () => {
    if (!symbol) return;
    
    setLoading(true);
    try {
      const { timeframe, start, end } = getTimeParams(selectedRange);
      
      const response = await axiosInstance.get(`${API_PATHS.PRICE.GET_CANDLES}`, {
        params: {
          symbol,
          timeframe,
          start,
          end
        }
      });

      // Transform API data to chart format (candles array from response)
      const candles = response.data.candles || [];
      const formattedData = candles.map(item => ({
        time: (selectedRange === '1D' || selectedRange === '5D')
          ? moment(item.ts).format('HH:mm')
          : moment(item.ts).format('DD/MM'),
        price: item.close,
        timestamp: item.ts
      }));

      setChartData(formattedData);

      // Calculate changeByTime and percentChangeByTime from candles
      if (candles.length > 0) {
        const firstPrice = candles[0].close;
        const lastPrice = candles[candles.length - 1].close;
        const changeByTime = lastPrice - firstPrice;
        const percentChangeByTime = (changeByTime / firstPrice) * 100;

        // Update summary data with calculated values using callback to avoid dependency
        setSummaryData(prevData => {
          if (!prevData) return null;
          return {
            ...prevData,
            changeByTime: changeByTime,
            percentChangeByTime: percentChangeByTime,
            time: selectedRange,
            timeRange: TIME_RANGE_LABELS[selectedRange]
          };
        });
      }

      console.log("Chart data loaded:", formattedData);

    } catch (error) {
      console.error("Error fetching chart data:", error);
      setChartData([]);
    } finally {
      setLoading(false);
    }
  };

  // Fetch summary data only when symbol changes
  useEffect(() => {
    fetchSummaryData();
    
    // Auto refresh summary every 5 minutes
    const intervalId = setInterval(() => {
      fetchSummaryData();
    }, 5 * 60 * 1000); // 5 minutes
    
    return () => clearInterval(intervalId);
  }, [symbol]);

  // Fetch chart data when symbol or range changes
  useEffect(() => {
    fetchChartData();
    
    // Auto refresh every 2 minutes
    const intervalId = setInterval(() => {
      fetchChartData();
    }, 2 * 60 * 1000); 
    
    // Cleanup interval on unmount or when dependencies change
    return () => clearInterval(intervalId);
  }, [symbol, selectedRange]);

  // Custom Tooltip
  const CustomTooltip = ({active, payload}) => {
    if(active && payload && payload.length){
      const item = payload[0].payload;
      
      // Format time based on range for detailed tooltip
      let displayTime = item.time;
      if (item.timestamp) {
        if (selectedRange === '1D' || selectedRange === '5D') {
          displayTime = moment(item.timestamp).format('HH:mm DD/MM');
        } else {
          displayTime = moment(item.timestamp).format('DD/MM/YYYY');
        }
      }
      
      return (
        <div className="bg-white shadow-md rounded-lg p-2 border border-gray-300">
          <p className='text-xs font-semibold text-purple-800 mb-1'>{displayTime}</p>
          <p className="text-sm text-gray-600">
            Giá: <span className='text-sm font-medium text-gray-900'>{addThousandsSeperator(item.price)}</span>
          </p>
        </div>
      )
    }
    return null;
  };

  const timeRanges = ['1D', '5D', '1M', '3M', 'YTD', '1Y', '5Y'];

  // Calculate Y-axis domain with ±5% padding
  const getYAxisDomain = () => {
    if (chartData.length === 0) return [0, 'auto'];
    
    const prices = chartData.map(item => item.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    
    const yDomainMin = minPrice - (minPrice * 0.005);
    const yDomainMax = maxPrice + (maxPrice * 0.005);
    
    return [yDomainMin, yDomainMax];
  };

  // Generate exactly 5 ticks for Y-axis (4 equal intervals)
  const getYAxisTicks = () => {
    if (chartData.length === 0) return [];
    
    const [min, max] = getYAxisDomain();
    const step = (max - min) / 4; // 4 intervals = 5 ticks
    
    return [
      min,
      min + step,
      min + step * 2,
      min + step * 3,
      max
    ];
  };

  // Generate exactly 5 ticks for X-axis from actual data
  const getXAxisTicks = () => {
    if (chartData.length === 0) return [];
    if (chartData.length <= 5) return chartData.map(item => item.time);
    
    const step = Math.floor((chartData.length - 1) / 4);
    return [
      chartData[0].time,
      chartData[step].time,
      chartData[step * 2].time,
      chartData[step * 3].time,
      chartData[chartData.length - 1].time
    ];
  };

  const chartColor = chartData.length > 0 
    ? (chartData[chartData.length - 1].price >= chartData[0].price ? '#22c55e' : '#ef4444')
    : '#875cf5';

  return (
    <StockMarket symbol={symbol}>
      {summaryData && <TitleStock data={summaryData} onAddToWatchlist={onAddToWatchlist}/>}
      
      {/* Time Range Filter Buttons */}
      <div className="card my-4">
        <div className="flex gap-2 mb-4 flex-wrap">
          {timeRanges.map((range) => (
            <button
              key={range}
              onClick={() => setSelectedRange(range)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedRange === range
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {range}
            </button>
          ))}
        </div>

        {/* Chart */}
        {loading ? (
          <div className="h-[300px] flex items-center justify-center text-gray-500">
            Đang tải dữ liệu...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-[300px] flex items-center justify-center text-gray-500">
            Không có dữ liệu cho mã {symbol}
          </div>
        ) : (
          <div className='bg-white'>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColor} stopOpacity={0.4}/>
                    <stop offset="95%" stopColor={chartColor} stopOpacity={0}/>
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0"/>
                <XAxis 
                  dataKey="time" 
                  tick={{ fontSize: 12, fill: "#555"}} 
                  stroke='none'
                  ticks={selectedRange === '5D' ? undefined : getXAxisTicks()}
                />
                <YAxis 
                  tick={{ fontSize: 12, fill: "#555"}} 
                  stroke='none'
                  domain={getYAxisDomain()}
                  ticks={getYAxisTicks()}
                  tickFormatter={(value) => addThousandsSeperator(value)} 
                />

                <Tooltip content={<CustomTooltip/>} />
                
                <Area
                  // type="monotone"
                  dataKey="price"
                  stroke={chartColor}
                  fill="url(#priceGradient)"
                  strokeWidth={3}
                  // dot={{ r: 1, fill: "#ab8df8" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </StockMarket>
  );
};

export default CustomLineChartStock;

// Test script for all interval/lookback combinations
const combinations = [
  { interval: '5m', lookback: '1d' },
  { interval: '5m', lookback: '3d' },
  { interval: '5m', lookback: '7d' },
  { interval: '5m', lookback: '14d' },
  { interval: '15m', lookback: '1d' },
  { interval: '15m', lookback: '3d' },
  { interval: '15m', lookback: '7d' },
  { interval: '15m', lookback: '14d' },
  { interval: '1h', lookback: '1d' },
  { interval: '1h', lookback: '3d' },
  { interval: '1h', lookback: '7d' },
  { interval: '1h', lookback: '14d' },
  { interval: '4h', lookback: '1d' },
  { interval: '4h', lookback: '3d' },
  { interval: '4h', lookback: '7d' },
  { interval: '4h', lookback: '14d' },
];

console.log('Test combinations:', combinations);

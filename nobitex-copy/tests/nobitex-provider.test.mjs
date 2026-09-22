import test from 'node:test';
import assert from 'node:assert/strict';
import {NobitexProvider} from '../src/providers/nobitex.mjs';

test('normalizes v3 orderbook with bids and asks in correct direction',()=>{
  const p=new NobitexProvider();
  const b=p.normalizeOrderbook('BTCIRT',{status:'ok',lastUpdate:1000,lastTradePrice:'104',bids:[['103','2'],['102','1']],asks:[['105','3'],['106','1']]});
  assert.equal(b.bids[0].price,103);
  assert.equal(b.asks[0].price,105);
  assert.equal(b.lastTradePrice,104);
});

test('computes spread and depth imbalance deterministically',()=>{
  const p=new NobitexProvider();
  const b=p.normalizeOrderbook('BTCIRT',{bids:[['100','2']],asks:[['102','1']],lastUpdate:Date.now()});
  const m=p.metrics(b,[{type:'buy',volume:3},{type:'sell',volume:1}]);
  assert.equal(m.mid,101);
  assert.equal(m.spread,2);
  assert.ok(m.orderbookImbalance>0);
  assert.equal(m.tradeImbalance,0.5);
});

test('classifies aligned orderbook and trade pressure',()=>{
  const p=new NobitexProvider();
  assert.equal(p.classify({orderbookImbalance:.22,tradeImbalance:.3}),'MOMENTUM_BUY_WATCH');
  assert.equal(p.classify({orderbookImbalance:-.3,tradeImbalance:-.2}),'SELL_PRESSURE');
});

test('deduplicates configured routes',()=>{
  const p=new NobitexProvider({apiBases:['https://api.nobitex.ir/','https://api.nobitex.ir']});
  assert.deepEqual(p.apiBases,['https://api.nobitex.ir']);
});

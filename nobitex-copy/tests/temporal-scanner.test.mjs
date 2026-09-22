import test from 'node:test';import assert from 'node:assert/strict';
import {temporalSummary} from '../src/services/market-scanner.mjs';

test('temporal summary confirms persistent actionable state',()=>{
  const s=temporalSummary([
    {state:'SELL_PRESSURE',tradeImbalance:-.8,obImbalance:-.3,attentionScore:70,spreadBps:2,freshMicrostructure:true},
    {state:'SELL_PRESSURE',tradeImbalance:-.6,obImbalance:-.2,attentionScore:68,spreadBps:3,freshMicrostructure:true},
    {state:'NEUTRAL',tradeImbalance:-.2,obImbalance:-.1,attentionScore:60,spreadBps:2,freshMicrostructure:true}
  ]);
  assert.equal(s.dominantState,'SELL_PRESSURE');assert.equal(s.temporalStatus,'CONFIRMED');assert.ok(s.persistence>=2/3);
});
test('temporal summary rejects one-off actionable state',()=>{
  const s=temporalSummary([
    {state:'REVERSAL_WATCH',tradeImbalance:.8,obImbalance:.2},
    {state:'NEUTRAL',tradeImbalance:-.1,obImbalance:.1},
    {state:'NEUTRAL',tradeImbalance:.1,obImbalance:-.1}
  ]);
  assert.equal(s.temporalStatus,'NEUTRAL');
});
test('temporal summary handles no data',()=>{assert.equal(temporalSummary([]).temporalStatus,'NO_DATA')});

test('confirmation requires fresh microstructure samples',()=>{
  const s=temporalSummary([
    {state:'SELL_PRESSURE',tradeImbalance:-.8,obImbalance:-.3,freshMicrostructure:true},
    {state:'SELL_PRESSURE',tradeImbalance:-.8,obImbalance:-.3,freshMicrostructure:false},
    {state:'SELL_PRESSURE',tradeImbalance:-.8,obImbalance:-.3,freshMicrostructure:false}
  ]);
  assert.notEqual(s.temporalStatus,'CONFIRMED');
  assert.ok(s.freshRatio<2/3);
});

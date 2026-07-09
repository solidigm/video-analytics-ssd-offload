# Created by Metrum AI for Solidigm

"""Multi-User Benchmark Service — k6 Docker orchestrator.

Generates N unique prompt+context payloads, launches a k6+xk6-sse Docker
container on the soln_default network, parses JSON metrics in real time,
and flushes KV caches after completion.
"""

# pylint: disable=too-many-lines

import asyncio
import copy
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from asyncio.subprocess import Process as AsyncProcess

import httpx

from src.services.cache_seed_service import CacheSeedService, cache_seed_service
from src.services.context_refresh_service import context_refresh_service
from src.services.prompt_utils import compact_context_for_model, build_football_analysis_prompt

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
LLM_BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k")
# Keep burst runs stable: huge per-request contexts can deadlock LMCache CPU eviction
# under concurrent load (requests stuck in waiting with zero running).
MULTI_USER_MAX_CONTEXT_CHARS = int(os.getenv("MULTI_USER_MAX_CONTEXT_CHARS", "220000"))
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
K6_TEMPLATE_FILE = os.getenv("K6_TEMPLATE_FILE", "k6_benchmark_template.js")
BENCHMARK_DISABLE_THINKING = os.getenv("BENCHMARK_DISABLE_THINKING", "0") == "1"
MAX_BENCHMARK_USERS = int(os.getenv("BENCHMARK_MAX_USERS", "500"))
# Keep benchmark runs bounded by default for stable completion.
# Set BENCHMARK_MAX_TOKENS="" explicitly to disable this cap.
_max_tok_raw = os.getenv("BENCHMARK_MAX_TOKENS", "512")
BENCHMARK_MAX_TOKENS: int | None = int(_max_tok_raw) if _max_tok_raw.strip() else None
BENCHMARK_PROM_RATE_WINDOW = os.getenv("BENCHMARK_PROM_RATE_WINDOW", "1m")
BENCHMARK_ACTIVE_DISK_DEVICE = os.getenv("BENCHMARK_ACTIVE_DISK_DEVICE", "nvme0n1")

# ── Prompt Pool (200 queries) ───────────────────────────────────────────────
# Indexed directly: MULTI_USER_PROMPTS[combo_idx] for deterministic seeding.
# First 50 are the original set; 51-199 extend coverage for >50 user runs.

MULTI_USER_PROMPTS = [
    # 0-12: Game overview and team form
    "Analyze these recent games from the context. Which players performed best overall (top rushers, receivers, defenders)? What formations were most effective for each team? Summarize key trends in 512 tokens using the full context provided.",
    "Break down play-calling patterns in these games: run/pass splits by down and distance, favorite formations on 3rd down, red zone tendencies. What's predictable? What's working? 512 tokens.",
    "Evaluate recent team form from these games. Is the offense trending up or down? Red zone efficiency? 3rd down conversion trends? Defensive consistency? Key momentum shifts? 512 tokens.",
    "In these recent games, which offensive/defensive matchups were most exploited? Did any player consistently beat their assignment? Coverage weaknesses? 512 tokens.",
    "Analyze formation effectiveness across these games. Which offensive sets had highest success rate? What defensive fronts worked best? 512 tokens.",
    "Analyze the provided games. How did offensive and defensive performance trend over time? Early vs late efficiency? Points per game trajectory? 512 tokens.",
    "From the provided games, identify the team MVP and top 5 impact players. Who was most consistent? Who had clutch performances? Statistical leaders? 512 tokens.",
    "Track formation usage evolution across the provided games. Did offensive/defensive schemes change? Which formations became more frequent? 512 tokens.",
    "Break down wins vs losses across these games. What differentiates winning games: turnover margin, rushing success, defensive stops? 512 tokens.",
    "Based on the context, what are this team's core strengths and critical weaknesses? Season-long patterns? 512 tokens.",
    "Using context from these games, detail key plays, turning points, offensive/defensive strategies, and momentum shifts. How did each drive end? 512 tokens.",
    "Analyze all scoring drives. What worked: tempo, formations, play types? Compare stalled drives vs successful ones. Red zone execution? 512 tokens.",
    "How did offensive and defensive game plans evolve? First half vs second half adjustments? Run/pass balance changes? Coverage schemes? 512 tokens.",
    # 13-19: Efficiency and unit metrics
    "Compare rushing vs passing efficiency across all provided games. Which approach gained more yards per attempt? 512 tokens.",
    "Evaluate red zone performance trends. Which formations scored most frequently inside the 20? 512 tokens.",
    "Which defensive formations generated the most pressure and turnovers across these games? 512 tokens.",
    "Analyze special teams impact on field position across these games. Kickoff return averages? Punt coverage? 512 tokens.",
    "Break down 3rd down conversion rates by formation and personnel grouping. Which combinations worked best? 512 tokens.",
    "Identify the most explosive offensive plays (20+ yards). What schemes and personnel set them up? 512 tokens.",
    "Compare first-half vs second-half performance trends. Do teams finish strong or fade? 512 tokens.",
    # 20-24: Situational and game-flow
    "Across all provided games, analyze drive efficiency: average plays and yards per drive, scoring drive percentage, and frequency of three-and-outs. Which factors most often killed drives? 512 tokens.",
    "Evaluate situational football across these games. How did the team perform on 3rd-and-short vs 3rd-and-long, and on 4th down attempts? Which play types and formations were most successful in those spots? 512 tokens.",
    "Using the full context, break down two-minute drill performance at the end of halves. How well did the offense manage clock and field position, and how did the defense hold up in hurry-up situations? 512 tokens.",
    "Analyze game-flow and momentum across the provided games. When did momentum swings typically occur (turnovers, big plays, special teams)? How well did the team respond after giving up a score? 512 tokens.",
    "Compare starting field position and drive outcomes across these games. How often did drives start in plus territory, and how efficiently did the team convert short fields into points? 512 tokens.",
    # 25-29: Player and unit evaluations
    "From all provided games, grade the offensive line's performance: pass protection, sack/pressure rate, and run-blocking success by direction (inside, off-tackle, outside). Which linemen or gaps were strengths or liabilities? 512 tokens.",
    "Evaluate the secondary's performance across these games. How often did they give up explosive passes, contested catches, or pass breakups and interceptions? Identify corners or safeties who consistently stood out. 512 tokens.",
    "Analyze linebacker play across the context: run fits, pursuit angles, coverage responsibilities, and blitz effectiveness. Which linebackers were most impactful down-to-down? 512 tokens.",
    "Across all games, identify the most reliable chain-movers on offense (3rd-down targets, go-to receivers, short-yardage backs). In what situations were they used, and how successful were they? 512 tokens.",
    "Using the context, evaluate tackling quality: frequency of missed tackles, yards after contact allowed, and which defenders were most/least dependable in open space. 512 tokens.",
    # 30-34: Scheme and tendency mining
    "From all provided games, analyze early-down tendencies. How often does the offense run vs pass on 1st and 2nd down, and how does that affect 3rd-down distances and conversion chances? 512 tokens.",
    "Study defensive play-calling tendencies across these games. When do they prefer to blitz versus rush four, and how does that change by down, distance, and field position? 512 tokens.",
    "Across the context, identify the most frequently used route concepts (slants, outs, screens, crossers, deep shots). Which concepts generated the highest success and explosive plays? 512 tokens.",
    "Analyze how often motion and shifts are used pre-snap across these games. Do they correlate with more successful plays or particular concepts like jet sweep or play-action? 512 tokens.",
    "Examine play-action usage versus straight dropback passing in the provided games. How does play-action impact yards per attempt, protection, and explosive play rate? 512 tokens.",
    # 35-39: Offensive structure and concepts
    "Across all games, analyze screen game usage (RB/WR/TE screens). How often were screens called, on what downs/distances, and how efficient were they compared to other pass concepts? 512 tokens.",
    "Evaluate the effectiveness of the inside run versus outside run game across these matches. Which gaps and directions produced the best yardage and success rate? 512 tokens.",
    "Analyze short passing (0-5 yards), intermediate (6-15), and deep shots (16+). How often does each depth get targeted, and which depth range is most efficient for this offense? 512 tokens.",
    "From the context, assess red-zone play-calling tendencies: run/pass split, favorite concepts, and how often the team calls play-action or rollouts near the goal line. 512 tokens.",
    "Analyze the offense's success on first down across these games. Are they setting up second-and-short or putting themselves behind the chains? Which plays work best on first down? 512 tokens.",
    # 40-44: Defensive schemes and stops
    "Using the full context, evaluate run defense: success stopping inside vs outside runs, frequency of tackles for loss, and which front alignments are most effective. 512 tokens.",
    "Analyze coverage performance across these games: frequency of man vs zone looks, how often receivers are left wide open, and which coverages best limit explosive passes. 512 tokens.",
    "From all games, identify blitz patterns: which positions blitz most often (LBs, DBs), on which downs, and how often blitzes produce sacks, pressures, or big plays allowed. 512 tokens.",
    "Analyze takeaway creation across all games: fumbles forced, interceptions, tipped balls. Which defenders are most involved, and what schemes tend to generate turnovers? 512 tokens.",
    "Across all games, evaluate discipline: penalty count and yards, typical penalty types, and when they occurred (3rd down, red zone, scoring plays). Which penalties were most damaging? 512 tokens.",
    # 45-49: Comparative and meta-level
    "Study turnover patterns: interceptions vs fumbles, where on the field they occurred, and how many points opponents scored off them. Are turnovers more a result of risky decisions or execution errors? 512 tokens.",
    "Across these games, analyze performance in one-score games versus blowouts. Does the team execute differently when the margin is tight compared to when the game is largely decided? 512 tokens.",
    "Using the full context, evaluate punt game performance: average punt distance, net yards after returns, frequency of punts inside the 20 vs touchbacks, and momentum impact. 512 tokens.",
    "Compare offensive performance in home vs away games within this context. Are there noticeable differences in scoring, efficiency, penalties, or pre-snap issues? 512 tokens.",
    "Summarize the overall identity displayed across these games on offense, defense, and special teams. If you had to describe this team's style in a scouting report for a new opponent, what would it say? 512 tokens.",
    # ── 50-69: Quarterback evaluation ──────────────────────────────────────────
    "Evaluate quarterback accuracy across all games: completion percentage by depth (short, intermediate, deep), accuracy under pressure vs clean pocket, and key overthrows or underthrows. 512 tokens.",
    "Analyze quarterback decision-making from the context. How often does the QB make the optimal read? Identify instances of holding the ball too long, forcing throws, or missing open receivers. 512 tokens.",
    "Assess quarterback pocket presence across these games. How does the QB handle interior pressure vs edge pressure? Does he climb the pocket or bail out? Impact on completion rate? 512 tokens.",
    "From these games, compare quarterback performance on play-action vs straight dropback. Which approach produces better efficiency, fewer sacks, and more explosive plays? 512 tokens.",
    "Evaluate quarterback performance under pressure across all games. Completion percentage, sack rate, scramble success, and throwaway frequency when facing blitz or rush. 512 tokens.",
    "Break down quarterback red-zone efficiency: TD/INT ratio, passer rating inside the 20, favorite targets, and tendency to throw high/low in tight windows. 512 tokens.",
    "Analyze quarterback cadence and pre-snap reads across these games. How often does the QB audible or check at the line? Do these adjustments lead to better play outcomes? 512 tokens.",
    "From the context, evaluate how effectively the quarterback distributes the ball. Target share by receiver, number of different players targeted per game, and any over-reliance on one option. 512 tokens.",
    "Across these games assess the quarterback's ability to extend plays. Yards after scramble, completions on extended plays, and whether extending plays leads to big gains or negative outcomes. 512 tokens.",
    "Study quarterback interception-worthy plays across the context. How many should have been picked off but were dropped? What situations and route concepts led to risky throws? 512 tokens.",
    # ── 60-69: Running back and ground game ────────────────────────────────────
    "Evaluate running back performance across these games: yards per carry, broken tackles, yards after contact, and receiving contributions. Which backs excelled in which roles? 512 tokens.",
    "Analyze the ground game by direction across all games: inside zone, outside zone, power, counter. Which run schemes generated the best efficiency and explosive runs? 512 tokens.",
    "From the context, assess running back pass protection. How often do backs pick up blitzes correctly? Are there noticeable whiff blocks or missed assignments? 512 tokens.",
    "Compare the effectiveness of lead-back carries vs change-of-pace back carries across these games. Does the team benefit from a committee approach or rely too heavily on one back? 512 tokens.",
    "Analyze goal-line and short-yardage rushing across all games. Conversion rate, formations used, and whether the team runs power, dive, or stretch near the goal line. 512 tokens.",
    "Evaluate the read-option and RPO game from the context. How often does the QB keep vs hand off? Are the reads correct, and which option produces better yardage? 512 tokens.",
    "Across these games, identify breakaway runs (15+ yards). What blocking schemes, personnel, and defensive weaknesses enabled them? 512 tokens.",
    "From the provided games, analyze running back usage by game situation: leading, trailing, and in close games. Does usage pattern change based on score? 512 tokens.",
    "Assess yards before contact across all games. Is the offensive line creating running lanes, or are backs having to make their own yardage? Which gaps are most productive? 512 tokens.",
    "Analyze how effectively the team uses the run to set up play-action. Is there a correlation between early rushing success and later play-action efficiency in these games? 512 tokens.",
    # ── 70-79: Wide receiver and passing targets ───────────────────────────────
    "Evaluate wide receiver performance across these games: catch rate, yards after catch, contested catch rate, and drops. Which receivers are most reliable? 512 tokens.",
    "From the context, analyze route-running quality. Which receivers consistently create separation? Who wins at the top of routes, and who relies on contested-catch ability? 512 tokens.",
    "Across all games, break down receiver usage by alignment: slot vs outside, left vs right. Are there tendencies the defense could exploit based on receiver positioning? 512 tokens.",
    "Analyze tight end contributions across these games: receiving targets, blocking grades, and versatility. How much does the tight end impact the passing and running game? 512 tokens.",
    "From the provided games, identify the top deep threat. Who gets the most targets beyond 20 yards, what's their catch rate, and how often do deep shots convert? 512 tokens.",
    "Evaluate receiver blocking in the run game across the context. Which wideouts are willing and effective blockers on run plays and screens? 512 tokens.",
    "Across these games, analyze targets on third down by receiver. Who is the go-to third-down target, what routes do they run, and how often do they convert? 512 tokens.",
    "From the context, assess how the passing game attacks different coverage shells. What route adjustments are made against Cover 2, Cover 3, and man coverage? 512 tokens.",
    "Break down yards after catch across all games. Which receivers gain the most YAC, and is it scheme-driven (screens, crossers) or individual ability (broken tackles)? 512 tokens.",
    "Analyze red-zone receiving targets across these games. Who gets the most looks inside the 20, what routes are called, and what's the touchdown conversion rate by receiver? 512 tokens.",
    # ── 80-89: Defensive line and pass rush ────────────────────────────────────
    "Evaluate defensive line play across all games: sack totals, pressures, QB hits, and run stops. Which linemen are most disruptive? 512 tokens.",
    "From the context, analyze pass rush techniques and moves. Which defenders use speed rush vs bull rush vs inside counter most effectively? 512 tokens.",
    "Across these games, assess interior defensive line performance. How well do nose tackles and defensive tackles hold the point of attack and collapse the pocket? 512 tokens.",
    "Analyze edge rusher effectiveness from the context. Win rate against offensive tackles, sack conversion from pressures, and impact on passing downs vs run downs. 512 tokens.",
    "From these games, evaluate how the defense generates pressure without blitzing. Four-man rush success rate, stunts and twists, and impact on quarterback decision-making. 512 tokens.",
    "Across the context, break down defensive line rotation and snap counts. Are starters getting worn down late in games? Does depth contribute meaningfully? 512 tokens.",
    "Analyze run-stuffing performance by defensive front alignment across these games. Which fronts (odd, even, bear) are most effective at stopping the run? 512 tokens.",
    "From all games, evaluate the defensive line's ability to set the edge on outside runs. How often do edge defenders maintain gap integrity vs get sealed inside? 512 tokens.",
    "Across these games, assess how the defensive line performs against misdirection and screen plays. Are they disciplined in their rush lanes? 512 tokens.",
    "From the context, identify the most impactful defensive lineman. Grade their all-around performance: run defense, pass rush, effort plays, and consistency. 512 tokens.",
    # ── 90-99: Coaching decisions and game management ──────────────────────────
    "Evaluate coaching decisions across these games: timeout usage, challenge flags, fourth-down calls, and end-of-half management. Which decisions were most impactful? 512 tokens.",
    "From the context, analyze halftime adjustments. How did offensive and defensive schemes change from first half to second half? Were adjustments effective? 512 tokens.",
    "Across all games, assess clock management in the final two minutes of each half. Were there wasted timeouts, poor clock decisions, or missed opportunities? 512 tokens.",
    "Analyze fourth-down decision-making across these games. When did the coach go for it vs punt/kick, and were those decisions analytically sound? 512 tokens.",
    "From the provided games, evaluate the coach's use of tempo. When did the offense speed up or slow down, and how did tempo changes affect play outcomes? 512 tokens.",
    "Across the context, assess personnel rotation decisions. Were the right players on the field in key situations? Any notable personnel mismatches or suboptimal groupings? 512 tokens.",
    "From these games, analyze the coaching staff's approach to game-opening scripts. How successful were the first 15 offensive plays in establishing the game plan? 512 tokens.",
    "Evaluate how the coaching staff manages the team when trailing vs leading. Do they become too conservative with a lead or too aggressive when behind? 512 tokens.",
    "Across all games, analyze the defensive coordinator's adjustments against spread and heavy formations. How quickly does the defense adapt to offensive tendencies? 512 tokens.",
    "From the context, grade the special teams coaching: coverage units, return blocking, fake punt/field goal execution, and overall special teams discipline. 512 tokens.",
    # ── 100-109: Turnover and takeaway analysis ────────────────────────────────
    "Across all games, build a complete turnover profile: types (INT, fumble, downs), field position, game situation, and how many led to opponent scores. 512 tokens.",
    "From the context, analyze ball security. Which ball carriers have the most fumbles, and are there common causes (strip attempts, loose carries, handoff issues)? 512 tokens.",
    "Evaluate interception-worthy passes across these games. How many were tipped at the line, poor decisions, miscommunications, or simply good defensive plays? 512 tokens.",
    "Across these games, assess turnover differential and its correlation with game outcomes. How often does the team winning the turnover battle also win the game? 512 tokens.",
    "From the provided games, analyze forced fumbles by the defense. Which defenders are best at stripping the ball, and in what situations do forced fumbles occur most? 512 tokens.",
    "Evaluate how the offense performs after committing a turnover. Do they bounce back quickly or do turnovers lead to extended scoring droughts? 512 tokens.",
    "Across all games, study defensive interception opportunities. How many drops or near-interceptions occurred, and which defenders had the best ball skills? 512 tokens.",
    "From the context, analyze turnover location and scoring impact. What percentage of turnovers in opponent territory led to points, and how efficient was the team at capitalizing? 512 tokens.",
    "Across these games, identify the most turnover-prone situations: down, distance, field position, and game clock. Are there predictable patterns? 512 tokens.",
    "From the provided games, evaluate the team's ability to protect the ball in the red zone. Are there fumbles or interceptions in scoring territory that cost points? 512 tokens.",
    # ── 110-119: Penalty and discipline analysis ───────────────────────────────
    "Across all games, compile a full penalty breakdown: types, positions responsible, down and distance, and game impact. Which penalties are most frequent? 512 tokens.",
    "From the context, analyze offensive holding penalties. How many negated big plays, and which linemen or positions are most responsible? 512 tokens.",
    "Evaluate defensive pass interference across these games. In what coverage situations do DPI calls occur, and how many converted stalled drives for the opponent? 512 tokens.",
    "Across these games, assess false start and illegal procedure frequency. Are there specific formations, personnel groupings, or game situations where they spike? 512 tokens.",
    "From the provided games, analyze penalties on critical downs (3rd down, 4th down, red zone). How often do penalties extend opponent drives or negate key plays? 512 tokens.",
    "Evaluate personal foul and unsportsmanlike conduct penalties across the context. Are there repeat offenders, and how costly are these penalties in terms of field position? 512 tokens.",
    "Across all games, compare penalty rates in the first half vs second half. Does discipline break down as the game progresses? 512 tokens.",
    "From the context, analyze how penalties affect scoring drives. How many touchdowns or field goals were aided by penalty yardage on the scoring drive? 512 tokens.",
    "Across these games, assess the impact of declined penalties. Were there situations where accepting a penalty would have been more beneficial than declining? 512 tokens.",
    "From the provided games, identify the most penalty-prone drives and analyze what went wrong. Did penalties cluster in certain game situations or against specific opponents? 512 tokens.",
    # ── 120-129: Special teams deep dive ───────────────────────────────────────
    "Evaluate kickoff coverage across all games: touchback rate, opponent starting field position, and tackles made inside the 25. Who are the top coverage specialists? 512 tokens.",
    "From the context, analyze punt return effectiveness. Average return yards, fair catch frequency, muffed punts, and big returns. Is the return game a weapon or liability? 512 tokens.",
    "Across these games, assess field goal kicking: accuracy by distance range (under 40, 40-49, 50+), misses in critical situations, and impact on game outcomes. 512 tokens.",
    "From the provided games, evaluate onside kick attempts and recovery rates. Were they called at appropriate times, and how did execution compare to expectations? 512 tokens.",
    "Analyze punt unit performance across all games: hang time, directional punting, coverage speed, and net punting average. How does the punt game affect field position? 512 tokens.",
    "Across the context, assess kick return performance. Average return yards, touchback decisions, big returns, and fumbles. Which returners are most effective? 512 tokens.",
    "From these games, evaluate blocking on special teams units. Are there consistent breakdowns in return blocking or coverage, and which personnel are responsible? 512 tokens.",
    "Across all games, analyze fake punt and fake field goal attempts. Were they well-designed and executed? How did they impact game momentum? 512 tokens.",
    "From the context, compare special teams performance in wins vs losses. Does special teams play have a measurable impact on game outcomes? 512 tokens.",
    "Evaluate special teams penalties across these games. How many holding, illegal block, and roughing penalties occurred, and how did they affect field position? 512 tokens.",
    # ── 130-139: Game situation and clutch performance ─────────────────────────
    "Across all games, analyze performance in the final five minutes of regulation. How does the team perform offensively and defensively in crunch time? 512 tokens.",
    "From the context, evaluate the team's record and performance when trailing entering the 4th quarter. What comeback patterns or tendencies emerge? 512 tokens.",
    "Across these games, assess performance on drives following opponent scores. How quickly and effectively does the team respond after giving up points? 512 tokens.",
    "From the provided games, analyze overtime or potential overtime situations. How does the team manage strategy and execution when the game is on the line? 512 tokens.",
    "Evaluate the team's performance after a turnover by the defense. How efficient is the offense at converting short-field opportunities into points? 512 tokens.",
    "Across the context, compare first-quarter and fourth-quarter performance metrics. Does the team start fast and fade, or build momentum throughout the game? 512 tokens.",
    "From these games, analyze performance when facing a two-score deficit. Does play-calling change appropriately, and how effective are desperation drives? 512 tokens.",
    "Across all games, evaluate performance on opening drives. How often does the team score on its first possession, and how does that correlate with winning? 512 tokens.",
    "From the context, analyze scoring runs and droughts. What are the longest scoring streaks and longest scoreless stretches, and what caused each? 512 tokens.",
    "Evaluate the team's performance in games decided by 7 points or fewer. How does execution in close games compare to blowouts across the context? 512 tokens.",
    # ── 140-149: Personnel groupings and packages ──────────────────────────────
    "Across all games, analyze 11 personnel (1 RB, 1 TE, 3 WR) usage and effectiveness. How often is it used, and what play types are most successful from this grouping? 512 tokens.",
    "From the context, evaluate 12 personnel (1 RB, 2 TE) effectiveness. Is the team better running or passing from two-TE sets? How does the defense react? 512 tokens.",
    "Across these games, assess 21 personnel (2 RB, 1 TE) usage. How effective is the two-back set in short-yardage, play-action, and standard run situations? 512 tokens.",
    "From the provided games, analyze empty backfield formations. How often does the team go empty, what's the success rate, and how does the defense typically respond? 512 tokens.",
    "Evaluate heavy personnel (22, 23 packages) usage across the context. Is the team effective with extra blockers in short-yardage and goal-line situations? 512 tokens.",
    "Across all games, analyze nickel and dime defensive packages. When does the defense add extra DBs, and how effective are these sub-packages against the pass and run? 512 tokens.",
    "From the context, assess how different personnel groupings perform on first down. Does the offense tip its play-call based on personnel, and does the defense react? 512 tokens.",
    "Across these games, evaluate the impact of jumbo packages near the goal line. Are extra linemen and tight ends effective at creating push for short-yardage scores? 512 tokens.",
    "From the provided games, analyze spread formations (10 personnel, 4-5 WR sets). How effective is the team when spreading the defense horizontally? 512 tokens.",
    "Evaluate how the defense adjusts personnel based on offensive formation. Are there delays in substitution, mismatches created, or confusion in personnel rotations? 512 tokens.",
    # ── 150-159: Tempo and pace analysis ───────────────────────────────────────
    "Across all games, analyze play tempo: time between plays by quarter, situation, and score differential. Does the team effectively vary its pace? 512 tokens.",
    "From the context, evaluate no-huddle offense effectiveness. How does the team perform when going up-tempo vs huddling? Impact on yards per play and scoring? 512 tokens.",
    "Across these games, assess how the defense handles up-tempo offenses. Do they get out of position, allow substitution issues, or struggle with communication? 512 tokens.",
    "From the provided games, analyze hurry-up situations late in halves. How efficiently does the offense execute the two-minute drill vs normal tempo? 512 tokens.",
    "Evaluate slow-tempo, ball-control drives across the context. How effective is the team at sustaining long drives that eat clock and maintain possession? 512 tokens.",
    "Across all games, compare offensive efficiency at different tempos. Are more plays per minute correlated with higher or lower yards per play? 512 tokens.",
    "From the context, analyze defensive fatigue indicators late in games. Do snaps per drive, time of possession, and opponent tempo correlate with defensive breakdowns? 512 tokens.",
    "Across these games, evaluate how tempo changes after a big play or turnover. Does the team capitalize on momentum with increased tempo? 512 tokens.",
    "From the provided games, assess the use of clock-killing drives in the second half. How effective is the team at protecting a lead through ball control? 512 tokens.",
    "Analyze how play-clock management affects offensive performance across these games. Are there delay-of-game penalties or rushed snaps that hurt execution? 512 tokens.",
    # ── 160-169: Defensive secondary and coverage ──────────────────────────────
    "Across all games, evaluate cornerback performance in man coverage. Press vs off technique, targets allowed, and passer rating against. Who is the shutdown corner? 512 tokens.",
    "From the context, analyze safety play in run support and coverage. Are safeties effective as the last line of defense while still contributing against the run? 512 tokens.",
    "Across these games, assess how the secondary handles crossing routes and pick plays. Are there communication breakdowns or switch issues? 512 tokens.",
    "From the provided games, evaluate Cover 3 effectiveness vs Cover 2. Which shell produces fewer explosive plays and better completion percentage against? 512 tokens.",
    "Analyze slot corner performance across the context. How well does the nickel defender handle quick-game concepts, screens, and intermediate routes from the slot? 512 tokens.",
    "Across all games, assess the secondary's performance on deep balls (20+ yards). How often are they in position, and what percentage of deep targets are completed? 512 tokens.",
    "From the context, evaluate defensive back ball skills. Pass breakups, interceptions, and contested catch rate allowed. Which DBs are best in trail technique? 512 tokens.",
    "Across these games, analyze how the secondary performs after a pass interference penalty. Do they become tentative or maintain aggressive coverage? 512 tokens.",
    "From the provided games, assess the secondary's performance in the red zone. How well do they defend back-shoulder fades, corner routes, and tight-window throws? 512 tokens.",
    "Evaluate how the secondary communicates and adjusts to motion and formation changes across all games. Are there blown coverages after pre-snap shifts? 512 tokens.",
    # ── 170-179: Advanced offensive concepts ───────────────────────────────────
    "Across all games, analyze RPO (run-pass option) usage. How often does the QB hand off vs pull and throw? Success rate by read type and defensive reaction? 512 tokens.",
    "From the context, evaluate jet sweep and end-around plays. Frequency, yardage, and whether they serve primarily as constraint plays or primary concepts. 512 tokens.",
    "Across these games, assess the use of bunch and stack formations. How do compressed receiver sets create matchup advantages or free up other targets? 512 tokens.",
    "From the provided games, analyze bootleg and rollout passing. Success rate, yards per attempt, and whether rollouts are more effective to one side vs the other. 512 tokens.",
    "Evaluate the use of pre-snap motion diagnostics across the context. How often does motion reveal coverage (man vs zone), and does the QB adjust accordingly? 512 tokens.",
    "Across all games, analyze designed QB runs and scrambles. How effective is the QB as a runner, and does the threat of QB runs help the overall run game? 512 tokens.",
    "From the context, assess trick plays and gadget plays. Were they well-timed, properly executed, and impactful on game momentum? 512 tokens.",
    "Across these games, evaluate the offset formation run game. How does shifting the back's alignment (strong, weak, pistol) affect hole creation and timing? 512 tokens.",
    "From the provided games, analyze combination routes: how do route combinations (mesh, drive, sail, smash) attack different coverages, and which combos work best? 512 tokens.",
    "Evaluate the team's approach to attacking the middle of the field across all games. How effectively do they use seam routes, crossing patterns, and TE targets over the middle? 512 tokens.",
    # ── 180-189: Conditioning, depth, and roster management ────────────────────
    "Across all games, analyze performance by quarter. Is there a drop-off in execution in the third or fourth quarter that suggests conditioning or depth issues? 512 tokens.",
    "From the context, evaluate backup player contributions. When starters were rested or injured, how did backups perform relative to starters? 512 tokens.",
    "Across these games, assess injury impact on team performance. Did losing key players measurably affect offensive or defensive output? 512 tokens.",
    "From the provided games, analyze defensive snap counts and rotation. Are certain defenders playing too many snaps, and does their performance decline late in games? 512 tokens.",
    "Evaluate how the team performs in back-to-back games or short weeks based on the context. Is there a fatigue factor visible in performance metrics? 512 tokens.",
    "Across all games, analyze the contribution of rookies and first-year players. Are they improving over the stretch of games, and where are they making the biggest impact? 512 tokens.",
    "From the context, assess the team's use of the inactive list and roster management decisions. Were the right players active for each game? 512 tokens.",
    "Across these games, evaluate the team's ability to overcome in-game injuries. How well does the next-man-up philosophy work in practice? 512 tokens.",
    "From the provided games, analyze positional depth. Which positions are deepest, and which are most vulnerable to injury or fatigue-related decline? 512 tokens.",
    "Evaluate the impact of player workload across these games. Are high-snap-count players showing signs of wear, and how does the staff manage their reps? 512 tokens.",
    # ── 190-199: Opponent and matchup analysis ─────────────────────────────────
    "Across all games, analyze how the team adjusts to different opponent styles. How does game planning differ against run-heavy vs pass-heavy opponents? 512 tokens.",
    "From the context, evaluate defensive adjustments against mobile quarterbacks. Does the defense contain the scramble effectively and adjust rush lanes? 512 tokens.",
    "Across these games, assess how the offense attacks different defensive fronts (3-4, 4-3, odd spacing). Which running and passing concepts work best against each? 512 tokens.",
    "From the provided games, analyze the team's performance against top-ranked opponents vs lower-ranked. Does quality of opposition measurably affect execution? 512 tokens.",
    "Evaluate how the team handles unique offensive schemes (triple option, air raid, pro-style) across the context. Which defensive adjustments are most effective? 512 tokens.",
    "Across all games, analyze offensive adjustments when the defense loads the box. How effectively does the team attack single-high safety looks? 512 tokens.",
    "From the context, assess how the team defends against screen-heavy offenses. Do they diagnose screens quickly and limit yards after catch? 512 tokens.",
    "Across these games, evaluate how the passing game adjusts when facing elite cornerbacks. Does the QB avoid targeting the best cover man, or does he attack? 512 tokens.",
    "From the provided games, analyze the team's ability to run the ball against stacked fronts. Do they find success with zone, gap, or counter schemes against loaded boxes? 512 tokens.",
    "Evaluate the team's overall adaptability across all games. How well does the coaching staff adjust game plans based on what the opponent shows, both pre-game and in-game? 512 tokens.",
]

assert len(MULTI_USER_PROMPTS) == 200, f"Expected 200 prompts, got {len(MULTI_USER_PROMPTS)}"

# ── BenchmarkRun Dataclass ──────────────────────────────────────────────────


@dataclass
class BenchmarkRun:  # pylint: disable=too-many-instance-attributes
    """In-memory state for a single benchmark execution."""

    run_id: str
    num_users: int
    run_dir: Path
    context_mode: str = "long_context"  # "quick" or "long_context"
    status: str = "running"
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    start_wall_time: float = field(default_factory=time.time)
    end_wall_time: Optional[float] = None
    process: Optional[AsyncProcess] = None
    container_name: str = ""
    cancelled: bool = False
    task: Optional[asyncio.Task] = None
    flush_status: str = "pending"  # pending | flushing | done | error

    # Per-target metric arrays
    ttfts: dict = field(default_factory=lambda: {"baseline": [], "lmcache": []})
    tpots: dict = field(default_factory=lambda: {"baseline": [], "lmcache": []})
    tps: dict = field(default_factory=lambda: {"baseline": [], "lmcache": []})
    dispatch_offsets_ms: dict = field(default_factory=lambda: {"baseline": [], "lmcache": []})
    total_tokens: dict = field(default_factory=lambda: {"baseline": 0, "lmcache": 0})
    errors: dict = field(default_factory=lambda: {"baseline": 0, "lmcache": 0})
    completed_requests: dict = field(default_factory=lambda: {"baseline": 0, "lmcache": 0})

    # Per-target first/last completion wall-times (for per-target duration)
    first_completion_wall: dict = field(default_factory=lambda: {"baseline": None, "lmcache": None})
    last_completion_wall: dict = field(default_factory=lambda: {"baseline": None, "lmcache": None})

    # Per-target wall-times: dispatch arrival → last request complete (for accurate throughput)
    first_request_wall: dict = field(default_factory=lambda: {"baseline": None, "lmcache": None})
    last_request_complete_wall: dict = field(default_factory=lambda: {"baseline": None, "lmcache": None})

    def compute_aggregates(self) -> dict:
        """Aggregate raw per-request metrics into UI-ready benchmark stats."""
        stop_time = self.end_time if self.end_time is not None else time.perf_counter()
        elapsed = stop_time - self.start_time

        def pcts(values):
            if not values:
                return {"p50": 0, "p90": 0, "p95": 0}
            s = sorted(values)
            n = len(s)
            return {
                "p50": s[int(n * 0.50)],
                "p90": s[min(int(n * 0.90), n - 1)],
                "p95": s[min(int(n * 0.95), n - 1)],
            }

        def spread(values):
            if not values:
                return {"min": 0, "p50": 0, "p95": 0, "max": 0}
            s = sorted(values)
            n = len(s)
            return {
                "min": s[0],
                "p50": s[int(n * 0.50)],
                "p95": s[min(int(n * 0.95), n - 1)],
                "max": s[-1],
            }

        def safe_avg(values):
            return sum(values) / len(values) if values else 0

        # Per-target duration: first request dispatch arrival → last request complete
        dur = {}
        for target in ("baseline", "lmcache"):
            t_start = self.first_request_wall[target]
            t_end = self.last_request_complete_wall[target]
            dur[target] = round(t_end - t_start, 1) if t_start and t_end else 0.0

        completed = {
            "baseline": int(self.completed_requests["baseline"]),
            "lmcache": int(self.completed_requests["lmcache"]),
        }

        return {
            "elapsed": round(elapsed, 1),
            "completed": completed,
            "total": self.num_users,
            "status": self.status,
            "ttft": {
                "baseline": pcts(self.ttfts["baseline"]),
                "lmcache": pcts(self.ttfts["lmcache"]),
            },
            "req_per_sec": {
                target: completed[target] / dur[target] if dur[target] > 0 else 0
                for target in ("baseline", "lmcache")
            },
            "tokens_per_sec": {
                "baseline": safe_avg(self.tps["baseline"]),
                "lmcache": safe_avg(self.tps["lmcache"]),
            },
            "tpot": {
                "baseline": safe_avg(self.tpots["baseline"]),
                "lmcache": safe_avg(self.tpots["lmcache"]),
            },
            "series": {
                "baseline_ttfts": list(self.ttfts["baseline"]),
                "lmcache_ttfts": list(self.ttfts["lmcache"]),
                "baseline_tps": list(self.tps["baseline"]),
                "lmcache_tps": list(self.tps["lmcache"]),
                "baseline_tpot": list(self.tpots["baseline"]),
                "lmcache_tpot": list(self.tpots["lmcache"]),
            },
            "dispatch_offset_ms": {
                "baseline": spread(self.dispatch_offsets_ms["baseline"]),
                "lmcache": spread(self.dispatch_offsets_ms["lmcache"]),
            },
            "total_tokens": dict(self.total_tokens),
            "errors": dict(self.errors),
            "per_target_duration": dur,
            "per_target_elapsed": {
                "baseline": (round(self.last_request_complete_wall["baseline"] - self.start_wall_time, 1) if self.last_request_complete_wall["baseline"] else round(elapsed, 1)),
                "lmcache": (round(self.last_request_complete_wall["lmcache"] - self.start_wall_time, 1) if self.last_request_complete_wall["lmcache"] else round(elapsed, 1)),
            },
        }


# ── Service ─────────────────────────────────────────────────────────────────


class MultiUserBenchmarkService:
    """Orchestrates benchmark runs, payload generation, and lifecycle state."""

    def __init__(self, cache_seed_svc: CacheSeedService):
        self.cache_seed_service = cache_seed_svc
        self._runs: dict[str, BenchmarkRun] = {}
        self._k6_image = os.getenv("K6_DOCKER_IMAGE", "soln-k6-sse")
        self._k6_network = os.getenv("K6_DOCKER_NETWORK", "soln_default")
        self._host_data_dir = os.getenv("BENCHMARK_HOST_DATA_DIR", "/data")
        self._k6_template = self._load_k6_template()

    # ── Template ────────────────────────────────────────────────────────────

    def _load_k6_template(self) -> str:
        paths = [
            Path(f"/app/configs/{K6_TEMPLATE_FILE}"),
            Path(__file__).parent.parent.parent / "configs" / K6_TEMPLATE_FILE,
        ]
        for p in paths:
            if p.exists():
                return p.read_text(encoding="utf-8")
        raise FileNotFoundError(f"{K6_TEMPLATE_FILE} not found")

    # ── Payload Generation ──────────────────────────────────────────────────

    def _compose_context(self, game_ids: list[str], all_contexts: dict[str, str]) -> str:
        parts: list[str] = []
        for gid in game_ids:
            narrative = all_contexts.get(gid, "")
            if not narrative:
                continue
            parts.append(f"\n\n=== GAME ANALYSIS: {gid} ===\n" "The following is a detailed play-by-play breakdown from game footage analysis.\n\n" f"{narrative}")
        return "".join(parts).strip()

    def _build_message(self, query: str, context: str) -> str:
        if context:
            return build_football_analysis_prompt(context, query)
        return f"You are an expert American football analyst.\n\nQuestion: {query}"

    def _context_budget_chars(self, _num_users: int, context_mode: str = "long_context") -> int:
        """Return fixed context budget per mode.

        Quick mode: ~60k chars (~15k tokens).
        Long context: ~200k chars (~50k tokens) — showcases SSD offloading.
        """
        if context_mode == "quick":
            return min(MULTI_USER_MAX_CONTEXT_CHARS, 60_000)
        # long_context
        return min(MULTI_USER_MAX_CONTEXT_CHARS, 200_000)

    def _generate_payloads(self, num_users: int, context_mode: str = "long_context") -> dict:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Build separate payload lists for each target.

        LMCache payloads — up to 200 seeded (prompt, game-selection) combos:
          combo_idx → random.Random(combo_idx) picks same games every run →
          LMCache SSD KV cache hits on subsequent runs and when N > num_combos repeats.

        Baseline payloads — identical content but unique UUID salt per request:
          "[sid-{uuid}]\\n{content}" prevents GPU prefix-cache hits (same
          approach as cold-cache scenario in Home.tsx:466).
        """
        all_contexts = self.cache_seed_service.get_all_contexts()
        all_game_ids = sorted(all_contexts.keys())  # stable ordering
        context_budget_chars = self._context_budget_chars(num_users, context_mode)
        logger.info(
            "Multi-user context budget: %d chars/request (users=%d)",
            context_budget_chars,
            num_users,
        )

        # Dynamic combo count: one unique combo per user, up to prompt pool size
        num_combos = min(num_users, len(MULTI_USER_PROMPTS))

        # ── Build LMCache combos (seeded, deterministic) ─────────────────────
        lmcache_combos: list[dict] = []
        for combo_idx in range(num_combos):
            rng = random.Random(combo_idx)
            prompt = MULTI_USER_PROMPTS[combo_idx]

            if all_game_ids:
                if context_mode == "quick":
                    num_games = rng.randint(5, min(10, len(all_game_ids)))  # 5-10 games
                else:
                    num_games = rng.randint(8, min(16, len(all_game_ids)))  # 8-16 games
                selected = rng.sample(all_game_ids, min(num_games, len(all_game_ids)))
                context = self._compose_context(selected, all_contexts)
                context, _ = compact_context_for_model(context, context_budget_chars)
            else:
                context = ""

            lm_combo: dict = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": self._build_message(prompt, context)}],
                "temperature": 0.3,
                "stream": True,
            }
            if BENCHMARK_MAX_TOKENS is not None:
                lm_combo["max_tokens"] = BENCHMARK_MAX_TOKENS
            if BENCHMARK_DISABLE_THINKING:
                lm_combo["chat_template_kwargs"] = {"enable_thinking": False}
            lmcache_combos.append(lm_combo)

        logger.info("Generated %d LMCache combos (seeded)", num_combos)

        # ── Build baseline combos: aggressively cache-busted ─────────────────
        # Cache prevention strategy:
        #   1. Unique UUID salt prefix (busts prefix-based matching)
        #   2. Shuffled game section order
        #   3. Paragraph-level shuffle within each game narrative
        #   4. Sliding window over the FULL context — each combo gets a different
        #      slice so the tokens surviving the char-budget cutoff are truly
        #      different per request (e.g. 100k full, 30k budget →
        #        combo 0 → [0:30k], combo 1 → [stride:stride+30k], …)
        #   5. Prompt injected at random position inside the sliced context
        baseline_combos: list[dict] = []
        for combo_idx, _lm in enumerate(lmcache_combos):
            brng = random.Random(f"baseline-{uuid.uuid4().hex}")
            prompt = MULTI_USER_PROMPTS[combo_idx]

            if all_game_ids:
                # Independent game selection per baseline combo (brng is UUID-seeded)
                if context_mode == "quick":
                    num_games = brng.randint(5, min(10, len(all_game_ids)))  # 5-10 games
                else:
                    num_games = brng.randint(8, min(16, len(all_game_ids)))  # 8-16 games
                selected = brng.sample(all_game_ids, min(num_games, len(all_game_ids)))

                # Build sections with paragraph-level shuffle inside each game
                sections: list[str] = []
                for gid in selected:
                    narrative = all_contexts.get(gid, "")
                    if not narrative:
                        continue
                    paragraphs = [p for p in narrative.split("\n\n") if p.strip()]
                    brng.shuffle(paragraphs)
                    shuffled_narrative = "\n\n".join(paragraphs)
                    sections.append(f"\n\n=== GAME ANALYSIS: {gid} ===\n" "The following is a detailed play-by-play breakdown " "from game footage analysis.\n\n" f"{shuffled_narrative}")

                # Inject prompt block at a random position among sections
                insert_pos = brng.randint(0, max(0, len(sections) - 1))
                prompt_section = "\n\nANALYSIS REQUEST: Using the surrounding game context, " "provide a thorough analysis for the following:\n" f"{prompt}\n"
                sections.insert(insert_pos, prompt_section)

                # Join into full (oversized) context
                full_context = "".join(sections).strip()
                full_len = len(full_context)

                # Sliding window: each combo takes a different slice
                if full_len > context_budget_chars:
                    surplus = full_len - context_budget_chars
                    stride = max(1, surplus // num_combos)
                    offset = (combo_idx * stride) % (surplus + 1)
                    context = full_context[offset : offset + context_budget_chars]
                else:
                    context = full_context
            else:
                context = ""

            salt = f"[sid-{uuid.uuid4().hex}]"
            content = f"{salt}\n{build_football_analysis_prompt(context, prompt)}"
            combo: dict = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": content}],
                "temperature": 0.3,
                "stream": True,
            }
            if BENCHMARK_MAX_TOKENS is not None:
                combo["max_tokens"] = BENCHMARK_MAX_TOKENS
            if BENCHMARK_DISABLE_THINKING:
                combo["chat_template_kwargs"] = {"enable_thinking": False}
            baseline_combos.append(combo)

        # Each user gets one combo, cycling if N > num_combos.
        # LMCache combos repeat as-is (enables SSD KV cache hits).
        # Baseline combos get a fresh UUID salt per-user to prevent
        # GPU prefix-cache hits even when the same combo cycles.
        lmcache_payloads = [lmcache_combos[i % num_combos] for i in range(num_users)]

        baseline_payloads: list[dict] = []
        for i in range(num_users):
            combo = baseline_combos[i % num_combos]
            if i >= num_combos:
                # Re-salt: deep-copy and replace the UUID prefix so the
                # content is unique even though the combo structure repeats.
                combo = copy.deepcopy(combo)
                old_content = combo["messages"][0]["content"]
                combo["messages"][0]["content"] = re.sub(
                    r"^\[sid-[0-9a-f]+\]",
                    f"[sid-{uuid.uuid4().hex}]",
                    old_content,
                    count=1,
                )
            baseline_payloads.append(combo)

        return {
            "lmcache": lmcache_payloads,
            "baseline": baseline_payloads,
        }

    # ── vLLM URLs ───────────────────────────────────────────────────────────

    def _get_vllm_url(self, target: str) -> str:
        if target == "baseline":
            return LLM_BASELINE_URL.rstrip("/") + "/chat/completions"
        return LLM_LMCACHE_URL.rstrip("/") + "/chat/completions"

    # ── Run Management ──────────────────────────────────────────────────────

    async def start_run(self, num_users: int, context_mode: str = "long_context") -> str:
        """Start a new benchmark run and launch the backing k6 container task."""
        if num_users < 1:
            raise ValueError("num_users must be >= 1")
        if num_users > MAX_BENCHMARK_USERS:
            raise ValueError(f"num_users must be <= {MAX_BENCHMARK_USERS}")

        active = [r for r in self._runs.values() if r.status == "running"]
        if active:
            raise ValueError("A benchmark is already running")

        # Verify k6 image exists
        check = await asyncio.create_subprocess_exec(
            "docker",
            "image",
            "inspect",
            self._k6_image,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await check.wait()
        if check.returncode != 0:
            raise RuntimeError(f"Docker image '{self._k6_image}' not found. " "Run 'docker compose build k6-sse' first.")

        run_id = uuid.uuid4().hex[:8]
        run_dir = Path(f"/data/benchmarks/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating %d payloads for benchmark %s (mode=%s)…", num_users, run_id, context_mode)
        payloads = self._generate_payloads(num_users, context_mode)
        (run_dir / "payloads.json").write_text(json.dumps(payloads))

        max_duration = os.getenv("BENCHMARK_MAX_DURATION", "172800s")
        script = self._k6_template
        script = script.replace("__BASELINE_URL__", self._get_vllm_url("baseline"))
        script = script.replace("__LMCACHE_URL__", self._get_vllm_url("lmcache"))
        script = script.replace("__MAX_DURATION__", max_duration)
        (run_dir / "script.js").write_text(script)

        run = BenchmarkRun(run_id=run_id, num_users=num_users, run_dir=run_dir, context_mode=context_mode)
        self._runs[run_id] = run
        run.task = asyncio.create_task(self._execute_k6(run))
        logger.info("Benchmark %s started with %d users (mode=%s)", run_id, num_users, context_mode)
        return run_id

    def get_run(self, run_id: str) -> Optional[BenchmarkRun]:
        """Return a benchmark run by id, if present."""
        return self._runs.get(run_id)

    def get_active_run(self) -> Optional[BenchmarkRun]:
        """Return the currently running benchmark, if one exists."""
        for r in self._runs.values():
            if r.status == "running":
                return r
        return None

    async def stop_run(self, run_id: str) -> None:
        """Request shutdown for a running benchmark by stopping its container."""
        run = self._runs.get(run_id)
        if not run or run.status != "running":
            return
        run.cancelled = True
        if run.container_name:
            logger.info("Stopping k6 container %s", run.container_name)
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "stop",
                run.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

    # ── k6 Execution ────────────────────────────────────────────────────────

    async def _execute_k6(self, run: BenchmarkRun) -> None:
        container_name = f"k6-benchmark-{run.run_id}"
        host_benchmark_dir = f"{self._host_data_dir}/benchmarks/{run.run_id}"

        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            self._k6_network,
            "-v",
            f"{host_benchmark_dir}:/benchmark:ro",
            "-w",
            "/benchmark",
            self._k6_image,
            "run",
            "--out",
            "json=-",
            "--quiet",
            "/benchmark/script.js",
        ]
        logger.info("Launching k6: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            run.process = proc
            run.container_name = container_name

            async for line in proc.stdout:
                if run.cancelled:
                    break
                text = line.decode().strip()
                if not text:
                    continue
                try:
                    point = json.loads(text)
                    self._process_k6_metric(run, point)
                except json.JSONDecodeError:
                    continue

            await proc.wait()

            if proc.returncode != 0 and not run.cancelled:
                stderr_bytes = await proc.stderr.read()
                stderr_text = stderr_bytes.decode().strip() if stderr_bytes else ""
                logger.error("k6 exited with code %d: %s", proc.returncode, stderr_text[:500])
                run.status = "error"
            else:
                run.status = "completed" if not run.cancelled else "cancelled"
            run.end_time = time.perf_counter()
            run.end_wall_time = time.time()

        except (OSError, subprocess.SubprocessError, ValueError, TypeError, RuntimeError) as e:
            logger.error("k6 execution error: %s", e)
            run.status = "error"
            run.end_time = time.perf_counter()
            run.end_wall_time = time.time()

        logger.info("Benchmark %s finished: %s", run.run_id, run.status)

        # Save disk I/O metrics for this run
        try:
            disk_metrics = await self.query_prometheus_vllm_metrics(
                start_unix=run.start_wall_time,
                end_unix=run.end_wall_time,
            )
            disk_data = {
                "device": BENCHMARK_ACTIVE_DISK_DEVICE,
                "totals": disk_metrics.get("disk_io_totals", {}),
                "instant": {
                    k: disk_metrics.get("instant", {}).get(k, {})
                    for k in (
                        "nvme_read_bw_bytes",
                        "nvme_write_bw_bytes",
                        "nvme_read_iops",
                        "nvme_write_iops",
                        "nvme_queue_depth",
                    )
                },
            }
            (run.run_dir / "disk_metrics.json").write_text(json.dumps(disk_data, indent=2))
            logger.info("Saved disk_metrics.json for benchmark %s", run.run_id)
        except (OSError, ValueError, TypeError, httpx.HTTPError) as e:
            logger.warning("Failed to save disk_metrics.json: %s", e)

        # Post-benchmark flush
        await self._flush_after_benchmark(run)

        # Schedule cleanup after 30 minutes
        loop = asyncio.get_event_loop()
        loop.call_later(1800, lambda: self._cleanup_run(run))

    # ── Metric Parsing ──────────────────────────────────────────────────────

    def _process_k6_metric(self, run: BenchmarkRun, point: dict) -> None:
        if point.get("type") != "Point":
            return
        metric = point.get("metric", "")
        value = point.get("data", {}).get("value", 0)
        target = point.get("data", {}).get("tags", {}).get("target", "unknown")

        if target not in ("baseline", "lmcache"):
            return

        if metric == "dispatch_offset_ms":
            run.dispatch_offsets_ms[target].append(value)
            now = time.time()
            if run.first_request_wall[target] is None:
                run.first_request_wall[target] = now
        elif metric == "ttft_seconds":
            run.ttfts[target].append(value)
            now = time.time()
            if run.first_completion_wall[target] is None:
                run.first_completion_wall[target] = now
            run.last_completion_wall[target] = now
            # Fallback: if dispatch_offset hasn't arrived yet
            if run.first_request_wall[target] is None:
                run.first_request_wall[target] = now
        elif metric == "tpot_ms":
            run.tpots[target].append(value)
        elif metric == "tokens_per_sec":
            run.tps[target].append(value)
        elif metric == "tokens_generated":
            run.total_tokens[target] += int(value)
            run.completed_requests[target] += 1
            # tokens_generated is the first metric emitted after sse.open() returns,
            # meaning the request stream is fully consumed (last token received).
            run.last_request_complete_wall[target] = time.time()
        elif metric == "error_rate" and value > 0:
            run.errors[target] += 1
            logger.warning(
                "Benchmark %s: %s request error (total errors: %d/%d)",
                run.run_id,
                target,
                run.errors[target],
                run.num_users,
            )

    # ── Prometheus Integration ──────────────────────────────────────────────

    async def query_prometheus_vllm_metrics(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks
        self,
        start_unix: Optional[float] = None,
        end_unix: Optional[float] = None,
        per_target_wall: Optional[dict] = None,
    ) -> dict:
        """PromQL-backed live + over-time metrics for baseline/lmcache/vlm jobs.

        Notes:
        - TTFT and TPOT use histogram means over BENCHMARK_PROM_RATE_WINDOW.
        - Request and token throughput use counter rates over BENCHMARK_PROM_RATE_WINDOW.
        """
        jobs_filter = '{job=~"vllm-(baseline|lmcache|vlm)"}'
        targets = ("baseline", "lmcache", "vlm")
        job_to_target = {
            "vllm-baseline": "baseline",
            "vllm-lmcache": "lmcache",
            "vllm-vlm": "vlm",
        }

        def zero_map() -> dict:
            return {t: 0.0 for t in targets}

        def to_float(value: str) -> float:
            try:
                v = float(value)
                return v if math.isfinite(v) else 0.0
            except (TypeError, ValueError):
                return 0.0

        def vector_to_target_map(result: list[dict]) -> dict:
            mapped = zero_map()
            for series in result:
                job = series.get("metric", {}).get("job")
                target = job_to_target.get(job)
                if not target:
                    continue
                point = series.get("value")
                if not point or len(point) < 2:
                    continue
                mapped[target] = to_float(point[1])
            return mapped

        def matrix_to_target_ts_maps(result: list[dict]) -> tuple[dict, set[int]]:
            per_target_ts = {t: {} for t in targets}
            all_ts: set[int] = set()

            for series in result:
                job = series.get("metric", {}).get("job")
                target = job_to_target.get(job)
                if not target:
                    continue
                for ts_raw, val_raw in series.get("values", []):
                    ts = int(float(ts_raw))
                    per_target_ts[target][ts] = to_float(val_raw)
                    all_ts.add(ts)

            return per_target_ts, all_ts

        # Scale rate window to benchmark duration for meaningful rates.
        # Use 1/4 of elapsed time, clamped to [15s, 5m].
        # Minimum 5s because vLLM scrape_interval is 2s and rate() needs ≥2 samples (≥4s).
        if start_unix is not None:
            elapsed_so_far = (end_unix or time.time()) - start_unix
            dynamic_secs = max(5, min(300, int(elapsed_so_far / 4)))
            w = f"{dynamic_secs}s"
        else:
            w = BENCHMARK_PROM_RATE_WINDOW

        # Canonical PromQL formulas for configurable rate-window instantaneous values
        # (all grouped by Prometheus "job" label).
        instant_queries = {
            "ttft_seconds": f"sum by(job) (rate(vllm:time_to_first_token_seconds_sum{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:time_to_first_token_seconds_count{jobs_filter}[{w}])), 1e-9)",
            "tpot_ms": f"1000 * sum by(job) (rate(vllm:request_time_per_output_token_seconds_sum{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:request_time_per_output_token_seconds_count{jobs_filter}[{w}])), 1e-9)",
            "requests_per_sec": f"sum by(job) (rate(vllm:request_success_total{jobs_filter}[{w}]))",
            "generation_tokens_per_sec": f"sum by(job) (rate(vllm:generation_tokens_total{jobs_filter}[{w}]))",
            "prompt_tokens_per_sec": f"sum by(job) (rate(vllm:prompt_tokens_total{jobs_filter}[{w}]))",
            "total_tokens_per_sec": f"sum by(job) (rate(vllm:prompt_tokens_total{jobs_filter}[{w}])) " f"+ sum by(job) (rate(vllm:generation_tokens_total{jobs_filter}[{w}]))",
            "requests_running": f"sum by(job) (vllm:num_requests_running{jobs_filter})",
            "requests_waiting": f"sum by(job) (vllm:num_requests_waiting{jobs_filter})",
            "kv_cache_usage_pct": f"100 * avg by(job) (vllm:kv_cache_usage_perc{jobs_filter})",
            "prefix_cache_hit_rate_pct": f"100 * sum by(job) (rate(vllm:prefix_cache_hits_total{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:prefix_cache_queries_total{jobs_filter}[{w}])), 1e-9)",
            "external_cache_hit_rate_pct": f"100 * sum by(job) (rate(vllm:external_prefix_cache_hits_total{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:external_prefix_cache_queries_total{jobs_filter}[{w}])), 1e-9)",
            # NVMe disk I/O metrics (from node-exporter)
            "nvme_read_bw_bytes": f'rate(node_disk_read_bytes_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_write_bw_bytes": f'rate(node_disk_written_bytes_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_read_iops": f'rate(node_disk_reads_completed_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_write_iops": f'rate(node_disk_writes_completed_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_queue_depth": f'node_disk_io_now{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}',
        }

        # Over-time series for charts in multi-user mode.
        range_queries = {
            "tpot_ms": f"1000 * sum by(job) (rate(vllm:request_time_per_output_token_seconds_sum{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:request_time_per_output_token_seconds_count{jobs_filter}[{w}])), 1e-9)",
            "requests_per_sec": f"sum by(job) (rate(vllm:request_success_total{jobs_filter}[{w}]))",
            "generation_tokens_per_sec": f"sum by(job) (rate(vllm:generation_tokens_total{jobs_filter}[{w}]))",
            "ttft_seconds": f"sum by(job) (rate(vllm:time_to_first_token_seconds_sum{jobs_filter}[{w}])) "
            f"/ clamp_min(sum by(job) (rate(vllm:time_to_first_token_seconds_count{jobs_filter}[{w}])), 1e-9)",
            # NVMe disk I/O timeseries
            "nvme_read_bw_bytes": f'rate(node_disk_read_bytes_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_write_bw_bytes": f'rate(node_disk_written_bytes_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_read_iops": f'rate(node_disk_reads_completed_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
            "nvme_write_iops": f'rate(node_disk_writes_completed_total{{device="{BENCHMARK_ACTIVE_DISK_DEVICE}"}}[{w}])',
        }

        result_payload = {
            "instant": {name: zero_map() for name in instant_queries},
            "series": {
                "window": {"start": None, "end": None, "step_seconds": None},
                "timestamps": [],
                **{name: zero_map() for name in range_queries},
            },
            # Average GPU power over benchmark window (from DCGM exporter).
            "gpu_power_avg": {"baseline": 0.0, "lmcache": 0.0},
            # Backward-compatible aliases used by existing frontend cards.
            "lmcache_cache_hit": 0.0,
            "baseline_cache_hit": 0.0,
            "lmcache_kv_usage": 0.0,
            "baseline_kv_usage": 0.0,
            "lmcache_requests_running": 0.0,
            "baseline_requests_running": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                for metric_name, promql in instant_queries.items():
                    try:
                        resp = await client.get(
                            f"{PROMETHEUS_URL}/api/v1/query",
                            params={"query": promql},
                        )
                        data = resp.json().get("data", {}).get("result", [])
                        result_payload["instant"][metric_name] = vector_to_target_map(data)
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        logger.debug("Prometheus instant query failed: %s", metric_name)

                if start_unix is not None:
                    end_ts = end_unix if end_unix is not None else time.time()
                    if end_ts < start_unix:
                        start_unix, end_ts = end_ts, start_unix
                    span = max(end_ts - start_unix, 1.0)
                    step_seconds = max(5, int(span / 120))

                    result_payload["series"]["window"] = {
                        "start": int(start_unix),
                        "end": int(end_ts),
                        "step_seconds": step_seconds,
                    }

                    metric_ts_maps: dict[str, dict] = {}
                    union_timestamps: set[int] = set()
                    for metric_name, promql in range_queries.items():
                        try:
                            resp = await client.get(
                                f"{PROMETHEUS_URL}/api/v1/query_range",
                                params={
                                    "query": promql,
                                    "start": start_unix,
                                    "end": end_ts,
                                    "step": step_seconds,
                                },
                            )
                            data = resp.json().get("data", {}).get("result", [])
                            per_target_ts, metric_timestamps = matrix_to_target_ts_maps(data)
                            if metric_timestamps:
                                metric_ts_maps[metric_name] = per_target_ts
                                union_timestamps.update(metric_timestamps)
                        except (httpx.HTTPError, ValueError, TypeError, KeyError):
                            logger.debug("Prometheus range query failed: %s", metric_name)

                    ordered_timestamps = sorted(union_timestamps)
                    result_payload["series"]["timestamps"] = ordered_timestamps

                    # Build per-target cutoff timestamps: zero out series data
                    # after each target's last request completes. This removes
                    # the Prometheus rate() trailing-window artifact where TPOT
                    # and Req/s show phantom activity after generation is done.
                    # Add one rate-window of grace so the final real data point
                    # isn't clipped (rate() looks backward, so the value AT the
                    # completion timestamp reflects the preceding window).
                    target_cutoff_ts: dict[str, int | None] = {t: None for t in targets}
                    if per_target_wall:
                        for tgt in targets:
                            tw = per_target_wall.get(tgt)
                            if tw and tw.get("end") is not None:
                                # Cutoff at completion timestamp itself;
                                # any data point after this is pure
                                # rate-window artifact, not real activity.
                                target_cutoff_ts[tgt] = int(tw["end"])

                    for metric_name, per_target_ts in metric_ts_maps.items():
                        # Forward-fill: carry last known value instead of 0.0
                        # so baseline doesn't appear to "drop off" when lmcache
                        # finishes first and has more Prometheus data points.
                        filled = {}
                        for target in targets:
                            target_data = per_target_ts[target]
                            cutoff = target_cutoff_ts.get(target)
                            arr = []
                            last_val = 0.0
                            for ts in ordered_timestamps:
                                # After target completed + 1 step, force to 0
                                if cutoff is not None and ts > cutoff:
                                    arr.append(0.0)
                                    continue
                                val = target_data.get(ts)
                                if val is not None:
                                    last_val = val
                                arr.append(last_val)
                            filled[target] = arr
                        result_payload["series"][metric_name] = filled

                    # ── GPU power averaged over each target's ACTIVE window ──
                    # Use per-target wall times so idle GPU time after a target
                    # finishes doesn't dilute its average power reading.
                    gpu_power = {"baseline": 0.0, "lmcache": 0.0}
                    try:
                        # GPU indices from env (comma-sep for TP>1), default to old layout
                        baseline_gpus = [g.strip() for g in os.getenv("BENCHMARK_BASELINE_GPU_IDS", "1").split(",")]
                        lmcache_gpus = [g.strip() for g in os.getenv("BENCHMARK_LMCACHE_GPU_IDS", "0").split(",")]
                        target_gpu_map = {"baseline": baseline_gpus, "lmcache": lmcache_gpus}
                        for target_name, gpu_ids in target_gpu_map.items():
                            # Per-target window: first_request → last_completion
                            t_start = start_unix
                            t_end = end_ts
                            if per_target_wall:
                                tw = per_target_wall.get(target_name)
                                if tw:
                                    if tw.get("start") is not None:
                                        t_start = tw["start"]
                                    if tw.get("end") is not None:
                                        t_end = tw["end"]
                            target_span = max(t_end - t_start, 1.0)
                            target_step = max(5, int(target_span / 120))
                            # Sum power across all GPUs for this target (TP>1)
                            total_power = 0.0
                            gpu_count = 0
                            for gpu_idx in gpu_ids:
                                resp = await client.get(
                                    f"{PROMETHEUS_URL}/api/v1/query_range",
                                    params={
                                        "query": f'DCGM_FI_DEV_POWER_USAGE{{gpu="{gpu_idx}"}}',
                                        "start": t_start,
                                        "end": t_end,
                                        "step": target_step,
                                    },
                                )
                                data = resp.json().get("data", {}).get("result", [])
                                if data:
                                    values = [to_float(v[1]) for v in data[0].get("values", [])]
                                    if values:
                                        total_power += sum(values) / len(values)
                                        gpu_count += 1
                            if gpu_count > 0:
                                gpu_power[target_name] = total_power  # total watts across all GPUs
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        logger.debug("GPU power range query failed")

                    result_payload["gpu_power_avg"] = {
                        "baseline": round(gpu_power["baseline"], 1),
                        "lmcache": round(gpu_power["lmcache"], 1),
                    }

                    # ── NVMe disk total bytes read/written (counter delta) ──
                    _disk_dev = BENCHMARK_ACTIVE_DISK_DEVICE
                    disk_totals = {"device": _disk_dev}
                    try:
                        for direction, counter in [
                            ("read", "node_disk_read_bytes_total"),
                            ("write", "node_disk_written_bytes_total"),
                        ]:
                            for ts, label in [(start_unix, "start"), (end_ts, "end")]:
                                resp = await client.get(
                                    f"{PROMETHEUS_URL}/api/v1/query",
                                    params={
                                        "query": f'{counter}{{device="{_disk_dev}"}}',
                                        "time": ts,
                                    },
                                )
                                data = resp.json().get("data", {}).get("result", [])
                                if data:
                                    disk_totals[f"{direction}_{label}"] = float(data[0]["value"][1])
                        for d in ("read", "write"):
                            s = disk_totals.get(f"{d}_start", 0)
                            e = disk_totals.get(f"{d}_end", 0)
                            disk_totals[f"total_{d}_gb"] = round((e - s) / 1e9, 2)

                        # R/W ratio
                        total_read = disk_totals.get("total_read_gb", 0)
                        total_write = disk_totals.get("total_write_gb", 0)
                        total_rw = total_read + total_write
                        if total_rw > 0:
                            disk_totals["read_write_ratio"] = f"{total_read/total_rw*100:.0f}:{total_write/total_rw*100:.0f}"
                        else:
                            disk_totals["read_write_ratio"] = "N/A"

                        # Average block size from instant rates
                        inst = result_payload["instant"]
                        for direction in ("read", "write"):
                            bw_key = f"nvme_{direction}_bw_bytes"
                            iops_key = f"nvme_{direction}_iops"
                            bw = inst.get(bw_key, {}).get("baseline", 0)
                            iops = inst.get(iops_key, {}).get("baseline", 0)
                            disk_totals[f"avg_{direction}_block_kb"] = round(bw / iops / 1024, 1) if iops > 0 else 0
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        logger.debug("Disk I/O totals query failed")
                    result_payload["disk_io_totals"] = disk_totals

        except (httpx.HTTPError, ValueError, TypeError, KeyError, RuntimeError) as e:
            logger.debug("Prometheus query batch failed: %s", e)

        result_payload["lmcache_cache_hit"] = result_payload["instant"]["prefix_cache_hit_rate_pct"]["lmcache"]
        result_payload["baseline_cache_hit"] = result_payload["instant"]["prefix_cache_hit_rate_pct"]["baseline"]
        result_payload["lmcache_kv_usage"] = result_payload["instant"]["kv_cache_usage_pct"]["lmcache"]
        result_payload["baseline_kv_usage"] = result_payload["instant"]["kv_cache_usage_pct"]["baseline"]
        result_payload["lmcache_requests_running"] = result_payload["instant"]["requests_running"]["lmcache"]
        result_payload["baseline_requests_running"] = result_payload["instant"]["requests_running"]["baseline"]

        return result_payload

    # ── Post-Benchmark Flush ────────────────────────────────────────────────

    async def _flush_after_benchmark(self, run: BenchmarkRun) -> None:
        """Flush only baseline GPU memory after benchmark.

        Intentionally skip LMCache flush to preserve SSD KV cache —
        subsequent benchmark runs benefit from cached combo KV blocks
        (seeded combos produce identical content every run → SSD cache hits).
        """
        run.flush_status = "flushing"
        try:
            context_refresh_service.ensure_books_loaded()
            baseline_ok = await context_refresh_service.flush_baseline()
            run.flush_status = "done"
            logger.info("Post-benchmark flush: baseline=%s (lmcache SSD preserved)", baseline_ok)
        except (RuntimeError, OSError, ValueError, TypeError) as e:
            run.flush_status = "error"
            logger.warning("Post-benchmark flush failed: %s", e)

    # ── Cleanup ─────────────────────────────────────────────────────────────

    def _cleanup_run(self, run: BenchmarkRun) -> None:
        shutil.rmtree(run.run_dir, ignore_errors=True)
        self._runs.pop(run.run_id, None)
        logger.info("Cleaned up benchmark run %s", run.run_id)


# Global instance
benchmark_service = MultiUserBenchmarkService(cache_seed_service)

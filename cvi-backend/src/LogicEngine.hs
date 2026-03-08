{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : LogicEngine
Description : The core CVI logic engine using Haskell pattern matching.

This module implements:
  * Risk-pattern definitions as algebraic data constructors
  * Pattern evaluation using Haskell's native pattern matching
  * Base CVI scoring (Exposure / Sensitivity / Adaptive Capacity)
  * Final CVI computation with pattern-penalty modifiers
-}
module LogicEngine
  ( computeAllCvi
  ) where

import           Data.Text (Text)
import qualified Data.Text as T
import           Types

-- ===========================================================================
--  2.1  Thresholds on the normalised [0,1] scale
-- ===========================================================================
-- 1 = most vulnerable, 0 = least vulnerable.

high, veryHigh :: Double
high     = 0.70
veryHigh = 0.85

-- ===========================================================================
--  2.2  Risk-Pattern Definitions  (Algebraic approach)
-- ===========================================================================
data RiskPattern
  = SinkingCity
  | ExposedCoast
  | CycloneCorridor
  | DefencelessShore
  | PovertyTrap
  | TripleThreat
  deriving (Show, Eq)

patternName :: RiskPattern -> Text
patternName SinkingCity      = "Sinking City"
patternName ExposedCoast     = "Exposed Coast"
patternName CycloneCorridor  = "Cyclone Corridor"
patternName DefencelessShore = "Defenceless Shore"
patternName PovertyTrap      = "Poverty Trap"
patternName TripleThreat     = "Triple Threat"

patternDescription :: RiskPattern -> Text
patternDescription SinkingCity =
  "Very low elevation + very high pop density \8212 massive flood exposure."
patternDescription ExposedCoast =
  "High erosion + high sea-level rise \8212 shoreline retreating fast."
patternDescription CycloneCorridor =
  "Frequent cyclones + poor drainage \8212 catastrophic flooding risk."
patternDescription DefencelessShore =
  "No mangrove protection + high erosion \8212 natural buffer absent."
patternDescription PovertyTrap =
  "Low income + frequent cyclones \8212 communities unable to recover."
patternDescription TripleThreat =
  "Low elevation + high erosion + high SLR \8212 worst physical combination."

patternPenalty :: RiskPattern -> Double
patternPenalty SinkingCity      = 0.25
patternPenalty ExposedCoast     = 0.20
patternPenalty CycloneCorridor  = 0.20
patternPenalty DefencelessShore = 0.15
patternPenalty PovertyTrap      = 0.15
patternPenalty TripleThreat     = 0.30

allPatterns :: [RiskPattern]
allPatterns =
  [ SinkingCity
  , ExposedCoast
  , CycloneCorridor
  , DefencelessShore
  , PovertyTrap
  , TripleThreat
  ]

-- ===========================================================================
--  2.3  Pattern-Matching Evaluation  (uses Haskell's native matching)
-- ===========================================================================

-- | Check whether a particular risk pattern matches for a given district.
matchesPattern :: DistrictData -> RiskPattern -> Bool

matchesPattern d SinkingCity =
  ddElevation d  >= veryHigh && ddPopDensity d >= veryHigh

matchesPattern d ExposedCoast =
  ddErosion d >= high && ddSlr d >= high

matchesPattern d CycloneCorridor =
  ddCycloneFreq d >= high && ddDrainageQuality d >= high

matchesPattern d DefencelessShore =
  ddMangroveCover d >= high && ddErosion d >= high

matchesPattern d PovertyTrap =
  ddIncome d >= high && ddCycloneFreq d >= high

matchesPattern d TripleThreat =
  ddElevation d >= high && ddErosion d >= high && ddSlr d >= high

-- | Evaluate a single district against ALL patterns.
evaluatePatterns :: DistrictData -> ([Text], Double, Text)
evaluatePatterns d =
  let matched   = filter (matchesPattern d) allPatterns
      names     = map patternName matched
      penalty   = min 0.60 (sum $ map patternPenalty matched)  -- cap at 0.60
      explain   = case matched of
                    [] -> "No high-risk patterns detected."
                    _  -> T.intercalate " | " $
                            map (\p -> patternName p <> ": " <> patternDescription p) matched
  in  (names, penalty, explain)


-- ===========================================================================
--  3.1  Base CVI Score  (Exposure + Sensitivity + Adaptive Capacity)
-- ===========================================================================
-- Pillar weights (must sum to 1.0)
wExposure, wSensitivity, wAdaptive :: Double
wExposure    = 0.40
wSensitivity = 0.35
wAdaptive    = 0.25

exposureScore :: DistrictData -> Double
exposureScore d = mean [ddElevation d, ddSlr d, ddCycloneFreq d]

sensitivityScore :: DistrictData -> Double
sensitivityScore d = mean [ddErosion d, ddPopDensity d, ddMangroveCover d]

adaptiveCapScore :: DistrictData -> Double
adaptiveCapScore d = mean [ddIncome d, ddDrainageQuality d]

baseCvi :: DistrictData -> Double
baseCvi d =
    exposureScore d   * wExposure
  + sensitivityScore d * wSensitivity
  + adaptiveCapScore d * wAdaptive

mean :: [Double] -> Double
mean xs = sum xs / fromIntegral (length xs)


-- ===========================================================================
--  3.2 & 3.3  Final CVI + Categorisation
-- ===========================================================================
categorise :: Double -> RiskLevel
categorise score
  | score >= 0.75 = VeryHigh
  | score >= 0.55 = High
  | score >= 0.35 = Moderate
  | otherwise     = Low


-- ===========================================================================
--  Public API: compute CVI for every district
-- ===========================================================================
computeCvi :: DistrictData -> CviResult
computeCvi d =
  let expo    = exposureScore d
      sensi   = sensitivityScore d
      adapt   = adaptiveCapScore d
      base    = baseCvi d
      (names, penalty, expl) = evaluatePatterns d
      final   = min 1.0 (base + penalty)
      cat     = riskLevelText (categorise final)
  in CviResult
       { crDistrict         = ddDistrict d
       , crState            = ddState d
       , crExposureScore    = roundTo 4 expo
       , crSensitivityScore = roundTo 4 sensi
       , crAdaptiveCapScore = roundTo 4 adapt
       , crBaseCvi          = roundTo 4 base
       , crPatternPenalty   = roundTo 2 penalty
       , crFinalCvi         = roundTo 4 final
       , crCategory         = cat
       , crMatchedPatterns  = names
       , crExplanation      = expl
       }

computeAllCvi :: [DistrictData] -> [CviResult]
computeAllCvi = map computeCvi

roundTo :: Int -> Double -> Double
roundTo n x =
  let factor = 10 ^ n :: Double
  in  fromIntegral (round (x * factor) :: Integer) / factor

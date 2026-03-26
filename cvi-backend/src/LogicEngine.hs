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
  , ndGainPenalty
  , ndGainPenaltyRule
  , applyNDGainToCVI
  , indiaNDGAIN
  ) where

import           Data.Text (Text)
import qualified Data.Text as T
import           Data.Map (Map, fromList)
import qualified Data.Map as Map
import           Types

-- | Pattern matching on adaptation gap → returns CVI penalty.
-- This is the core function that makes ND-GAIN a TARGET DATASET.
ndGainPenalty :: Double -> Double -> Double
ndGainPenalty vulnerability readiness
  | gap > 0.15 = 0.12  -- Critical adaptation deficit
  | gap > 0.09 = 0.07  -- High adaptation deficit (India matches here)
  | gap > 0.05 = 0.03  -- Moderate adaptation deficit
  | gap <= 0.0 = -0.05 -- Readiness exceeds vulnerability (bonus)
  | otherwise  = 0.01  -- Low deficit
  where gap = vulnerability - readiness

-- | Describe which guard matched (for frontend display).
ndGainPenaltyRule :: Double -> Double -> Text
ndGainPenaltyRule vulnerability readiness
  | gap > 0.15 = "gap > 0.15 \8594 CRITICAL DEFICIT \8594 penalty = +0.12"
  | gap > 0.09 = "gap > 0.09 \8594 HIGH DEFICIT \8594 penalty = +0.07"
  | gap > 0.05 = "gap > 0.05 \8594 MODERATE DEFICIT \8594 penalty = +0.03"
  | gap <= 0.0 = "gap \8804 0.0 \8594 READINESS SURPLUS \8594 bonus = \8722 0.05"
  | otherwise  = "gap \8804 0.05 \8594 LOW DEFICIT \8594 penalty = +0.01"
  where gap = vulnerability - readiness

-- | Apply ND-GAIN penalty to base CVI score, capped at 1.0.
applyNDGainToCVI :: Double -> Double -> Double -> Double
applyNDGainToCVI baseCVI vulnerability readiness =
  min 1.0 (baseCVI + ndGainPenalty vulnerability readiness)

-- | India ND-GAIN 2023 constant — the actual target dataset used in penalty computation.
indiaNDGAIN :: NDGAINData
indiaNDGAIN = NDGAINData
  { ndScore             = 45.46
  , ndVulnerability     = 0.4846
  , ndReadiness         = 0.3937
  , ndAdaptationGap     = 0.4846 - 0.3937
  , ndAdaptationPenalty = ndGainPenalty 0.4846 0.3937
  , ndGlobalRank        = 112
  , ndTotalCountries    = 187
  , ndRankPercentile    = 40
  , ndYear              = 2023
  , ndTrend             = "improving"
  , ndVulnTrend         = "decreasing"
  , ndReadyTrend        = "increasing"
  , ndPenaltyRule       = ndGainPenaltyRule 0.4846 0.3937
  , ndInterpretation    = "India ranks 112/187. Adaptation gap 0.0909 triggers HIGH DEFICIT rule. Penalty +0.07 added to district CVI score."
  , ndRegionalContext   = "Better than Bangladesh (#174), Pakistan (#151). Similar to Sri Lanka (#111). Worse than China (#39), Indonesia (#98)."
  }

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

geomorphologyData :: Map String String
geomorphologyData = fromList
    [ ("chennai",           "Sandy Beach")
    , ("mumbai",            "Rocky Cliff")
    , ("kochi",             "Mangrove")
    , ("visakhapatnam",     "Sandy Beach")
    , ("puri",              "Sandy Beach")
    , ("mangaluru",         "Sandy Beach")
    , ("kakinada",          "Mangrove")
    , ("bapatla",           "Sandy Beach")
    , ("kolkata",           "Delta")
    , ("surat",             "Mudflat")
    , ("kanyakumari",       "Rocky Cliff")
    , ("thiruvananthapuram","Sandy Beach")
    , ("kozhikode",         "Sandy Beach")
    , ("alappuzha",         "Mangrove")
    , ("kollam",            "Sandy Beach")
    , ("puducherry",        "Sandy Beach")
    , ("cuddalore",         "Mangrove")
    , ("nagapattinam",      "Sandy Beach")
    , ("nellore",           "Mudflat")
    , ("ongole",            "Sandy Beach")
    , ("bhubaneswar",       "Sandy Beach")
    , ("paradip",           "Delta")
    , ("balasore",          "Sandy Beach")
    , ("kendrapara",        "Mangrove")
    , ("udupi",             "Rocky Cliff")
    , ("raigad",            "Rocky Cliff")
    , ("ratnagiri",         "Rocky Cliff")
    , ("sindhudurg",        "Rocky Cliff")
    , ("goa",               "Sandy Beach")
    , ("bharuch",           "Mudflat")
    , ("navsari",           "Sandy Beach")
    , ("digha",             "Sandy Beach")
    , ("sundarbans",        "Mangrove")
    , ("srikakulam",        "Sandy Beach")
    , ("vizianagaram",      "Sandy Beach")
    , ("guntur",            "Mudflat")
    , ("krishna",           "Mangrove")
    , ("east godavari",     "Mangrove")
    , ("west godavari",     "Mangrove")
    ]

shorelineChangeData :: Map String Double
shorelineChangeData = fromList
    [ ("chennai",           -1.2)
    , ("mumbai",            -0.8)
    , ("kochi",             -0.5)
    , ("visakhapatnam",     -1.8)
    , ("puri",              -2.1)
    , ("mangaluru",         -0.9)
    , ("kakinada",          -0.7)
    , ("bapatla",           -1.5)
    , ("kolkata",           -3.2)
    , ("surat",             -1.1)
    , ("kanyakumari",        0.3)
    , ("thiruvananthapuram", -0.6)
    , ("kozhikode",         -0.8)
    , ("alappuzha",         -1.9)
    , ("kollam",            -0.7)
    , ("puducherry",        -1.3)
    , ("cuddalore",         -1.6)
    , ("nagapattinam",      -2.4)
    , ("nellore",           -1.0)
    , ("ongole",            -1.2)
    , ("bhubaneswar",       -0.9)
    , ("paradip",           -2.8)
    , ("balasore",          -1.4)
    , ("kendrapara",        -2.1)
    , ("udupi",              0.2)
    , ("raigad",            -0.4)
    , ("ratnagiri",          0.1)
    , ("sindhudurg",         0.3)
    , ("goa",               -0.6)
    , ("bharuch",           -0.5)
    , ("navsari",           -0.8)
    , ("digha",             -3.5)
    , ("sundarbans",        -4.2)
    , ("srikakulam",        -1.6)
    , ("vizianagaram",      -1.1)
    , ("guntur",            -0.9)
    , ("krishna",           -1.7)
    , ("east godavari",     -1.4)
    , ("west godavari",     -1.3)
    ]

tidalRangeData :: Map String Double
tidalRangeData = fromList
    [ ("chennai",            1.0)
    , ("mumbai",             5.2)
    , ("kochi",              0.8)
    , ("visakhapatnam",      1.1)
    , ("puri",               1.6)
    , ("mangaluru",          1.4)
    , ("kakinada",           1.2)
    , ("bapatla",            1.0)
    , ("kolkata",            4.5)
    , ("surat",              6.8)
    , ("kanyakumari",        0.6)
    , ("thiruvananthapuram", 0.7)
    , ("kozhikode",          0.9)
    , ("alappuzha",          0.8)
    , ("kollam",             0.7)
    , ("puducherry",         1.0)
    , ("cuddalore",          1.1)
    , ("nagapattinam",       1.3)
    , ("nellore",            1.2)
    , ("ongole",             1.1)
    , ("bhubaneswar",        1.8)
    , ("paradip",            2.1)
    , ("balasore",           3.4)
    , ("kendrapara",         3.2)
    , ("udupi",              1.3)
    , ("raigad",             4.8)
    , ("ratnagiri",          3.9)
    , ("sindhudurg",         2.8)
    , ("goa",                2.1)
    , ("bharuch",            7.2)
    , ("navsari",            5.8)
    , ("digha",              3.6)
    , ("sundarbans",         4.8)
    , ("srikakulam",         1.2)
    , ("vizianagaram",       1.1)
    , ("guntur",             1.4)
    , ("krishna",            1.6)
    , ("east godavari",      1.5)
    , ("west godavari",      1.4)
    ]

socialVulnData :: Map String Double
socialVulnData = fromList
    [ ("chennai",            0.38)
    , ("mumbai",             0.42)
    , ("kochi",              0.28)
    , ("visakhapatnam",      0.52)
    , ("puri",               0.65)
    , ("mangaluru",          0.31)
    , ("kakinada",           0.55)
    , ("bapatla",            0.61)
    , ("kolkata",            0.58)
    , ("surat",              0.45)
    , ("kanyakumari",        0.35)
    , ("thiruvananthapuram", 0.29)
    , ("kozhikode",          0.32)
    , ("alappuzha",          0.41)
    , ("kollam",             0.38)
    , ("puducherry",         0.33)
    , ("cuddalore",          0.58)
    , ("nagapattinam",       0.62)
    , ("nellore",            0.54)
    , ("ongole",             0.57)
    , ("bhubaneswar",        0.48)
    , ("paradip",            0.66)
    , ("balasore",           0.63)
    , ("kendrapara",         0.68)
    , ("udupi",              0.27)
    , ("raigad",             0.49)
    , ("ratnagiri",          0.44)
    , ("sindhudurg",         0.39)
    , ("goa",                0.31)
    , ("bharuch",            0.47)
    , ("navsari",            0.43)
    , ("digha",              0.69)
    , ("sundarbans",         0.74)
    , ("srikakulam",         0.64)
    , ("vizianagaram",       0.61)
    , ("guntur",             0.53)
    , ("krishna",            0.51)
    , ("east godavari",      0.56)
    , ("west godavari",      0.54)
    ]

geomorphologyRisk :: String -> Double
geomorphologyRisk "Sandy Beach" = 0.8
geomorphologyRisk "Mudflat"     = 0.9
geomorphologyRisk "Delta"       = 1.0
geomorphologyRisk "Mangrove"    = 0.5
geomorphologyRisk "Rocky Cliff" = 0.3
geomorphologyRisk _             = 0.6

-- New robust CVI formula with 7 factors
robustCVI :: DistrictData -> Double
robustCVI d =
    let elevScore     = ddElevation d
        slrScore      = ddSlr d
        popScore      = ddPopDensity d
        geoRaw        = Map.findWithDefault "Sandy Beach" (T.unpack $ T.toLower $ ddDistrict d) geomorphologyData
        geoScore      = geomorphologyRisk geoRaw
        shoreRaw      = Map.findWithDefault 0.0 (T.unpack $ T.toLower $ ddDistrict d) shorelineChangeData
        shoreScore    = min 1.0 (abs shoreRaw / 5.0)
        tidalRaw      = Map.findWithDefault 0.0 (T.unpack $ T.toLower $ ddDistrict d) tidalRangeData
        tidalScore    = min 1.0 (tidalRaw / 8.0)
        socialScore   = Map.findWithDefault 0.0 (T.unpack $ T.toLower $ ddDistrict d) socialVulnData
    in  (elevScore  * 0.20) +
        (slrScore   * 0.20) +
        (popScore   * 0.15) +
        (geoScore   * 0.15) +
        (shoreScore * 0.15) +
        (tidalScore * 0.10) +
        (socialScore * 0.05)

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
      -- Step 1: compute base CVI from physical / geo data
      baseCVI = robustCVI d
      -- Step 2: evaluate existing pattern-matching risk patterns
      (names, penalty, expl) = evaluatePatterns d
      baseWithPatterns = min 1.0 (baseCVI + penalty)
      -- Step 3: apply ND-GAIN adaptation penalty on top (the critical step)
      final   = applyNDGainToCVI baseWithPatterns
                  (ndVulnerability indiaNDGAIN)
                  (ndReadiness     indiaNDGAIN)
      cat     = riskLevelText (categorise final)
  in CviResult
       { crDistrict         = ddDistrict d
       , crState            = ddState d
       , crExposureScore    = roundTo 4 expo
       , crSensitivityScore = roundTo 4 sensi
       , crAdaptiveCapScore = roundTo 4 adapt
       , crBaseCvi          = roundTo 4 baseCVI
       , crPatternPenalty   = roundTo 2 penalty
       , crFinalCvi         = roundTo 4 final
       , crCategory         = cat
       , crMatchedPatterns  = names
       , crExplanation      = expl
       , crNDGain           = indiaNDGAIN
       }

computeAllCvi :: [DistrictData] -> [CviResult]
computeAllCvi = map computeCvi

roundTo :: Int -> Double -> Double
roundTo n x =
  let factor = 10 ^ n :: Double
  in  fromIntegral (round (x * factor) :: Integer) / factor

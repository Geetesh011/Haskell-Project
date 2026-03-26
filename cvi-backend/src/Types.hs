{-# LANGUAGE DeriveGeneric     #-}
{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Types
Description : Algebraic data types for the CVI engine.

Defines the input (DistrictData) and output (CviResult) types
with Aeson JSON instances for serialisation / deserialisation.
-}
module Types
  ( DistrictData (..)
  , CviResult (..)
  , NDGAINData (..)
  , RiskLevel (..)
  , riskLevelText
  ) where

import           Data.Aeson   (FromJSON (..), ToJSON (..), object, withObject,
                               (.:), (.=))
import           Data.Text    (Text)
import           GHC.Generics (Generic)

-- ===========================================================================
--  ND-GAIN Data (lives here to avoid circular dependency with LogicEngine)
-- ===========================================================================
data NDGAINData = NDGAINData
  { ndScore             :: !Double
  , ndVulnerability     :: !Double
  , ndReadiness         :: !Double
  , ndAdaptationGap     :: !Double
  , ndAdaptationPenalty :: !Double
  , ndGlobalRank        :: !Int
  , ndTotalCountries    :: !Int
  , ndRankPercentile    :: !Int
  , ndYear              :: !Int
  , ndTrend             :: !Text
  , ndVulnTrend         :: !Text
  , ndReadyTrend        :: !Text
  , ndPenaltyRule       :: !Text
  , ndInterpretation    :: !Text
  , ndRegionalContext   :: !Text
  } deriving (Show, Generic)

instance ToJSON NDGAINData

-- ===========================================================================
--  Input: Normalised district data received from Python  (all values 0-1)
-- ===========================================================================
data DistrictData = DistrictData
  { ddDistrict        :: !Text
  , ddState           :: !Text
  , ddElevation       :: !Double   -- 1 = most vulnerable (lowest elevation)
  , ddErosion         :: !Double   -- 1 = highest erosion
  , ddSlr             :: !Double   -- 1 = fastest SLR
  , ddPopDensity      :: !Double   -- 1 = highest pop density
  , ddIncome          :: !Double   -- 1 = lowest income (inverted)
  , ddCycloneFreq     :: !Double   -- 1 = most cyclones
  , ddMangroveCover   :: !Double   -- 1 = least mangrove (inverted)
  , ddDrainageQuality :: !Double   -- 1 = worst drainage (inverted)
  } deriving (Show, Generic)

instance FromJSON DistrictData where
  parseJSON = withObject "DistrictData" $ \v -> DistrictData
    <$> v .: "district"
    <*> v .: "state"
    <*> v .: "elevation_m"
    <*> v .: "erosion_rate_m_yr"
    <*> v .: "slr_mm_yr"
    <*> v .: "pop_density_km2"
    <*> v .: "income_level_inr"
    <*> v .: "cyclone_freq"
    <*> v .: "mangrove_cover_pct"
    <*> v .: "drainage_quality"

-- ===========================================================================
--  Output: CVI result for each district
-- ===========================================================================
data RiskLevel
  = Low
  | Moderate
  | High
  | VeryHigh
  deriving (Show, Eq, Ord, Generic)

riskLevelText :: RiskLevel -> Text
riskLevelText Low      = "Low"
riskLevelText Moderate = "Moderate"
riskLevelText High     = "High"
riskLevelText VeryHigh = "Very High"

data CviResult = CviResult
  { crDistrict        :: !Text
  , crState           :: !Text
  , crExposureScore   :: !Double
  , crSensitivityScore :: !Double
  , crAdaptiveCapScore :: !Double
  , crBaseCvi         :: !Double
  , crPatternPenalty  :: !Double
  , crFinalCvi        :: !Double
  , crCategory        :: !Text
  , crMatchedPatterns :: ![Text]
  , crExplanation     :: !Text
  , crNDGain          :: !NDGAINData
  } deriving (Show, Generic)

instance ToJSON CviResult where
  toJSON r = object
    [ "district"           .= crDistrict r
    , "state"              .= crState r
    , "exposure_score"     .= crExposureScore r
    , "sensitivity_score"  .= crSensitivityScore r
    , "adaptive_cap_score" .= crAdaptiveCapScore r
    , "base_cvi"           .= crBaseCvi r
    , "pattern_penalty"    .= crPatternPenalty r
    , "final_cvi"          .= crFinalCvi r
    , "category"           .= crCategory r
    , "matched_patterns"   .= crMatchedPatterns r
    , "explanation"        .= crExplanation r
    , "ndgain"             .= crNDGain r
    ]

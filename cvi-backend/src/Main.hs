{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Main
Description : CLI entry point for the CVI backend.

Reads normalised district JSON from stdin, runs the logic engine,
and writes CVI results as JSON to stdout.
-}
module Main (main) where

import qualified Data.Aeson           as Aeson
import qualified Data.ByteString.Lazy as BL
import           System.IO            (hPutStrLn, stderr)

import           LogicEngine          (computeAllCvi)
import           Types                (DistrictData)

main :: IO ()
main = do
  hPutStrLn stderr "[Haskell CVI Engine] Reading normalised data from stdin..."
  input <- BL.getContents
  case Aeson.eitherDecode input :: Either String [DistrictData] of
    Left err -> do
      hPutStrLn stderr $ "[ERROR] Failed to parse JSON input: " ++ err
      BL.putStr $ Aeson.encode (Aeson.object ["error" Aeson..= err])
    Right districts -> do
      hPutStrLn stderr $
        "[Haskell CVI Engine] Parsed " ++ show (length districts) ++ " districts. Computing CVI..."
      let results = computeAllCvi districts
      BL.putStr (Aeson.encode results)
      hPutStrLn stderr "[Haskell CVI Engine] Done. Results written to stdout."

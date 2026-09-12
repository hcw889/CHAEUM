import type { BuildingLocation, MatchCandidate, RankLabel } from "./types";

export const RANK_NUMBERS: Record<NonNullable<RankLabel>, number> = { gold: 1, silver: 2, bronze: 3 };
export type LocatedMatch = MatchCandidate & { location: BuildingLocation };

export function hasMapLocation(match: MatchCandidate): match is LocatedMatch {
  const location = match.location;
  return !!location
    && Number.isFinite(location.lat) && Math.abs(location.lat) <= 90
    && Number.isFinite(location.lng) && Math.abs(location.lng) <= 180;
}

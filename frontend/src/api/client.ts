import axios, { AxiosError } from 'axios'

// ---------------------------------------------------------------------------
// Base URL — falls back to localhost backend when env var is absent
// ---------------------------------------------------------------------------
const BASE_URL: string =
  (import.meta.env['VITE_BACKEND_URL'] as string | undefined) ??
  'http://127.0.0.1:8000'

const http = axios.create({ baseURL: BASE_URL })

// ---------------------------------------------------------------------------
// Types — matching backend schemas (backend/app/schemas.py)
// ---------------------------------------------------------------------------

export interface TeamsResponse {
  teams: string[]
}

export interface ModelStatusResponse {
  half_life: number
  n_draws: number
  trained_at: string
  model_id: string
}

export interface StrengthEntry {
  team: string
  group: string
  score: number
  att: number
  def: number
}

export interface StrengthResponse {
  ranking: StrengthEntry[]
}

export interface TeamState {
  pts: number
  gf: number
  ga: number
  gd: number
  g: number
}

export interface TourneyGroups {
  [group: string]: string[]
}

export interface TourneyState {
  groups: TourneyGroups
  state: Record<string, TeamState>
  remaining: Array<{ home: string; away: string; group: string }>
}

export interface SimulationResult {
  team: string
  group: string
  grpW: number
  ko: number
  r16: number
  qf: number
  sf: number
  final: number
  champ: number
}

export interface SimulateTournamentRequest {
  n: number
  seed?: number
  rho?: number
  model_id?: string
}

export interface SimulateTournamentResponse {
  results: SimulationResult[]
}

export interface SimulateMatchRequest {
  home: string
  away: string
  n_per_draw?: number
  rho?: number
  model_id?: string
}

export interface SimulateMatchResponse {
  home: string
  away: string
  pH: number
  pD: number
  pA: number
}

export interface Scoreline {
  h: number
  a: number
  prob: number
}

export interface SimulateModalRequest {
  home: string
  away: string
  top_k?: number
  model_id?: string
}

export interface SimulateModalResponse {
  home: string
  away: string
  scorelines: Scoreline[]
}

export interface H2HRequest {
  home: string
  away: string
  knockout?: boolean
  top_k?: number
  model_id?: string
}

export interface H2HResponse {
  home: string
  away: string
  ci_lower: number
  ci_median: number
  ci_upper: number
  top_scorelines: Scoreline[]
}

export interface MarketOddsEntry {
  home: string
  away: string
  h: number
  d: number | null
  a: number
}

export interface MarketOddsResponse {
  odds: MarketOddsEntry[]
}

export interface R32Match {
  id: number
  home: string
  home_slot: string
  away: string
  away_slot: string
  pH: number
  pD: number
  pA: number
  score_h: number | null
  score_a: number | null
  played: boolean
  uncertain: boolean
  home_coach: string | null
  away_coach: string | null
}

export interface R32Response {
  matches: R32Match[]
}

export interface RetrainRequest {
  half_life: number
  n_draws: number
}

export interface RetrainResponse {
  model_id: string
  trained_at: string
  half_life: number
  n_draws: number
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class APIError extends Error {
  code: string
  status: number
  details: unknown

  constructor(code: string, status: number, message: string, details?: unknown) {
    super(message)
    this.name = 'APIError'
    this.code = code
    this.status = status
    this.details = details
  }
}

function normalizeError(err: unknown): never {
  if (err instanceof AxiosError && err.response) {
    const payload = err.response.data as {
      error?: { code?: string; message?: string; details?: unknown }
    }
    const e = payload?.error ?? {}
    throw new APIError(
      e.code ?? 'UNKNOWN_ERROR',
      err.response.status,
      e.message ?? `Request failed: ${err.response.status}`,
      e.details,
    )
  }
  throw err
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getTeams(): Promise<TeamsResponse> {
  try {
    const { data } = await http.get<TeamsResponse>('/teams')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function getModelStatus(): Promise<ModelStatusResponse> {
  try {
    const { data } = await http.get<ModelStatusResponse>('/model/status')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function getStrength(): Promise<StrengthResponse> {
  try {
    const { data } = await http.get<StrengthResponse>('/model/strength')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function getTourneyState(): Promise<TourneyState> {
  try {
    const { data } = await http.get<TourneyState>('/tourney/state')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function putTourneyState(body: TourneyState): Promise<TourneyState> {
  try {
    const { data } = await http.put<TourneyState>('/tourney/state', body)
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function simulateTournament(
  req: SimulateTournamentRequest,
): Promise<SimulateTournamentResponse> {
  try {
    const { data } = await http.post<SimulateTournamentResponse>(
      '/simulate/tournament',
      req,
    )
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function simulateMatch(
  req: SimulateMatchRequest,
): Promise<SimulateMatchResponse> {
  try {
    const { data } = await http.post<SimulateMatchResponse>('/simulate/match', req)
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function simulateModal(
  req: SimulateModalRequest,
): Promise<SimulateModalResponse> {
  try {
    const { data } = await http.post<SimulateModalResponse>('/simulate/modal', req)
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function simulateH2H(req: H2HRequest): Promise<H2HResponse> {
  try {
    const { data } = await http.post<H2HResponse>('/simulate/h2h', req)
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function getMarketOdds(): Promise<MarketOddsResponse> {
  try {
    const { data } = await http.get<MarketOddsResponse>('/market/odds')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function postRetrain(req: RetrainRequest): Promise<RetrainResponse> {
  try {
    const { data } = await http.post<RetrainResponse>('/model/retrain', req)
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function getR32(): Promise<R32Response> {
  try {
    const { data } = await http.get<R32Response>('/tourney/r32')
    return data
  } catch (err) {
    normalizeError(err)
  }
}

export async function putR32Result(
  matchId: number,
  scoreH: number,
  scoreA: number,
): Promise<{ ok: boolean }> {
  try {
    const { data } = await http.put<{ ok: boolean }>(`/tourney/r32/${matchId}`, {
      score_h: scoreH,
      score_a: scoreA,
    })
    return data
  } catch (err) {
    normalizeError(err)
  }
}

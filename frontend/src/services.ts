import {
  getAvailableCompetitions,
  ingestEvents,
  ingestSoccerData,
  loginLoginAccessToken,
  loginRecoverPassword,
  loginRecoverPasswordHtmlContent,
  loginResetPassword,
  loginTestToken,
  privateCreateUser,
  readCompetitions,
  readEvents,
  readFrames,
  readLineups,
  readMatches,
  readMatchTeams,
  readPlayerSeasonStats,
  readPlayers,
  usersCreateUser,
  usersDeleteUser,
  usersDeleteUserMe,
  usersReadUserById,
  usersReadUserMe,
  usersReadUsers,
  usersRegisterUser,
  usersUpdatePasswordMe,
  usersUpdateUser,
  usersUpdateUserMe,
  utilsHealthCheck,
  utilsTestEmail,
} from "./client/sdk.gen"
import type {
  BodyLoginLoginAccessToken as AccessToken,
  CompetitionsPublic,
  EventsPublic,
  Frames360Public,
  IngestResult,
  LineupsPublic,
  Message,
  NewPassword,
  PlayerSeasonStats,
  PlayersPublic,
  PrivateUserCreate,
  SoccerMatchesPublic,
  SoccerTeamsPublic,
  StatsBombCompetition,
  Token,
  UpdatePassword,
  UserCreate,
  UserPublic,
  UserRegister,
  UsersPublic,
  UserUpdate,
  UserUpdateMe,
} from "./client/types.gen"

export class UsersService {
  public static async readUsers(options?: {
    skip?: number
    limit?: number
    query?: { skip?: number; limit?: number }
  }): Promise<UsersPublic> {
    const q = options && "query" in options ? options.query : options
    const res = await usersReadUsers({ query: q })
    return res.data
  }

  public static async readUserMe(): Promise<UserPublic> {
    const res = await usersReadUserMe()
    return res.data
  }

  public static async createUser(options: {
    body?: UserCreate
    requestBody?: UserCreate
  }): Promise<UserPublic> {
    const body = options.body || options.requestBody!
    const res = await usersCreateUser({ body })
    return res.data
  }

  public static async registerUser(options: {
    body?: UserRegister
    requestBody?: UserRegister
  }): Promise<UserPublic> {
    const body = options.body || options.requestBody!
    const res = await usersRegisterUser({ body })
    return res.data
  }

  public static async updateUserMe(options: {
    body?: UserUpdateMe
    requestBody?: UserUpdateMe
  }): Promise<UserPublic> {
    const body = options.body || options.requestBody!
    const res = await usersUpdateUserMe({ body })
    return res.data
  }

  public static async updatePasswordMe(options: {
    body?: UpdatePassword
    requestBody?: UpdatePassword
  }): Promise<Message> {
    const body = options.body || options.requestBody!
    const res = await usersUpdatePasswordMe({ body })
    return res.data
  }

  public static async deleteUserMe(): Promise<Message> {
    const res = await usersDeleteUserMe()
    return res.data
  }

  public static async readUserById(options: {
    userId?: string
    path?: { user_id: string }
  }): Promise<UserPublic> {
    const user_id = options.path?.user_id || options.userId!
    const res = await usersReadUserById({ path: { user_id } })
    return res.data
  }

  public static async updateUser(options: {
    userId?: string
    path?: { user_id: string }
    body?: UserUpdate
    requestBody?: UserUpdate
  }): Promise<UserPublic> {
    const user_id = options.path?.user_id || options.userId!
    const body = options.body || options.requestBody!
    const res = await usersUpdateUser({ path: { user_id }, body })
    return res.data
  }

  public static async deleteUser(options: {
    userId?: string
    path?: { user_id: string }
  }): Promise<Message> {
    const user_id = options.path?.user_id || options.userId!
    const res = await usersDeleteUser({ path: { user_id } })
    return res.data
  }
}

export class LoginService {
  public static async loginAccessToken(options: {
    body?: AccessToken
    formData?: AccessToken
  }): Promise<Token> {
    const body = options.body || options.formData!
    const res = await loginLoginAccessToken({ body })
    return res.data
  }

  public static async testToken(): Promise<UserPublic> {
    const res = await loginTestToken()
    return res.data
  }

  public static async recoverPassword(options: {
    email?: string
    path?: { email: string }
  }): Promise<Message> {
    const email = options.path?.email || options.email!
    const res = await loginRecoverPassword({ path: { email } })
    return res.data
  }

  public static async resetPassword(options: {
    body?: NewPassword
    requestBody?: NewPassword
  }): Promise<Message> {
    const body = options.body || options.requestBody!
    const res = await loginResetPassword({ body })
    return res.data
  }

  public static async recoverPasswordHtmlContent(options: {
    email?: string
    path?: { email: string }
  }): Promise<string> {
    const email = options.path?.email || options.email!
    const res = await loginRecoverPasswordHtmlContent({ path: { email } })
    return res.data as unknown as string
  }
}

export class SoccerService {
  public static async readCompetitions(options?: {
    skip?: number
    limit?: number
    hasMatches?: boolean
    hasEvents?: boolean
    has_matches?: boolean
    has_events?: boolean
    query?: {
      skip?: number
      limit?: number
      has_matches?: boolean
      has_events?: boolean
    }
  }): Promise<CompetitionsPublic> {
    const raw = options && "query" in options ? options.query : options
    const query = raw
      ? {
          skip: raw.skip,
          limit: raw.limit,
          has_matches: raw.has_matches ?? (raw as any)?.hasMatches,
          has_events: raw.has_events ?? (raw as any)?.hasEvents,
        }
      : undefined
    const res = await readCompetitions({ query })
    return res.data
  }

  public static async getAvailableCompetitions(): Promise<
    Array<StatsBombCompetition>
  > {
    const res = await getAvailableCompetitions()
    return res.data
  }

  public static async ingestSoccerData(): Promise<IngestResult> {
    const res = await ingestSoccerData()
    return res.data
  }

  public static async readMatches(options?: {
    competitionSeasonId?: string | null
    competition_season_id?: string | null
    hasEvents?: boolean
    has_events?: boolean
    teamName?: string | null
    team_name?: string | null
    teamId?: string | null
    team_id?: string | null
    skip?: number
    limit?: number
    query?: {
      competition_season_id?: string | null
      has_events?: boolean
      team_name?: string | null
      team_id?: string | null
      skip?: number
      limit?: number
    }
  }): Promise<SoccerMatchesPublic> {
    const raw = options && "query" in options ? options.query : options
    const query = raw
      ? {
          competition_season_id:
            raw.competition_season_id ?? (raw as any)?.competitionSeasonId,
          has_events: raw.has_events ?? (raw as any)?.hasEvents,
          team_name: raw.team_name ?? (raw as any)?.teamName,
          team_id: raw.team_id ?? (raw as any)?.teamId,
          skip: raw.skip,
          limit: raw.limit,
        }
      : undefined
    const res = await readMatches({ query })
    return res.data
  }

  public static async readMatchTeams(options?: {
    competitionSeasonId?: string | null
    competition_season_id?: string | null
    hasEvents?: boolean
    has_events?: boolean
    query?: {
      competition_season_id?: string | null
      has_events?: boolean
    }
  }): Promise<SoccerTeamsPublic> {
    const raw = options && "query" in options ? options.query : options
    const query = raw
      ? {
          competition_season_id:
            raw.competition_season_id ?? (raw as any)?.competitionSeasonId,
          has_events: raw.has_events ?? (raw as any)?.hasEvents,
        }
      : undefined
    const res = await readMatchTeams({ query })
    return res.data
  }

  public static async readEvents(options: {
    matchId?: string
    match_id?: string
    skip?: number
    limit?: number
    typeName?: string | null
    type_name?: string | null
    team?: string | null
    period?: number | null
    player?: string | null
    possession?: number | null
    team_id?: string | null
    query?: {
      match_id: string
      skip?: number
      limit?: number
      type_name?: string | null
      team?: string | null
      period?: number | null
      player?: string | null
      possession?: number | null
      team_id?: string | null
    }
  }): Promise<EventsPublic> {
    const raw = options && "query" in options ? options.query : options
    const match_id = (raw?.match_id || (raw as any)?.matchId)!
    const query = {
      match_id,
      skip: raw?.skip,
      limit: raw?.limit,
      type_name: raw?.type_name ?? (raw as any)?.typeName,
      team: raw?.team,
      period: raw?.period,
      player: raw?.player,
      possession: raw?.possession,
      team_id: raw?.team_id,
    }
    const res = await readEvents({ query })
    return res.data
  }

  public static async ingestEvents(options?: {
    competitionStatsbombId?: number
    competition_statsbomb_id?: number
    seasonId?: number
    season_id?: number
    query?: {
      competition_statsbomb_id?: number
      season_id?: number
    }
  }): Promise<Record<string, string>> {
    const raw = options && "query" in options ? options.query : options
    const query = raw
      ? {
          competition_statsbomb_id:
            raw.competition_statsbomb_id ??
            (raw as any)?.competitionStatsbombId,
          season_id: raw.season_id ?? (raw as any)?.seasonId,
        }
      : undefined
    const res = await ingestEvents({ query })
    return res.data
  }

  public static async readLineups(options: {
    matchId?: string
    match_id?: string
    query?: { match_id: string }
  }): Promise<LineupsPublic> {
    const raw = options && "query" in options ? options.query : options
    const match_id = (raw?.match_id || (raw as any)?.matchId)!
    const res = await readLineups({ query: { match_id } })
    return res.data
  }

  public static async readFrames(options: {
    matchId?: string
    match_id?: string
    skip?: number
    limit?: number
    query?: {
      match_id: string
      skip?: number
      limit?: number
    }
  }): Promise<Frames360Public> {
    const raw = options && "query" in options ? options.query : options
    const match_id = (raw?.match_id || (raw as any)?.matchId)!
    const query = {
      match_id,
      skip: raw?.skip,
      limit: raw?.limit,
    }
    const res = await readFrames({ query })
    return res.data
  }

  public static async readPlayers(options?: {
    nameSearch?: string | null
    name_search?: string | null
    skip?: number
    limit?: number
    query?: {
      name_search?: string | null
      skip?: number
      limit?: number
    }
  }): Promise<PlayersPublic> {
    const raw = options && "query" in options ? options.query : options
    const query = raw
      ? {
          name_search: raw.name_search ?? (raw as any)?.nameSearch,
          skip: raw.skip,
          limit: raw.limit,
        }
      : undefined
    const res = await readPlayers({ query })
    return res.data
  }

  public static async readPlayerSeasonStats(options: {
    playerId?: string
    player_id?: string
    seasonId?: string | null
    season_id?: string | null
    path?: { player_id: string }
    query?: { season_id?: string | null }
  }): Promise<PlayerSeasonStats> {
    const player_id =
      options.path?.player_id || options.player_id || options.playerId!
    const rawQuery = options.query
    const season_id =
      rawQuery?.season_id ?? options.season_id ?? options.seasonId
    const res = await readPlayerSeasonStats({
      path: { player_id },
      query: season_id ? { season_id } : undefined,
    })
    return res.data
  }
}

export class UtilsService {
  public static async healthCheck(): Promise<boolean> {
    const res = await utilsHealthCheck()
    return res.data
  }

  public static async testEmail(options: {
    emailTo?: string
    email_to?: string
    query?: { email_to: string }
  }): Promise<Message> {
    const raw = options && "query" in options ? options.query : options
    const email_to = (raw?.email_to || (raw as any)?.emailTo)!
    const res = await utilsTestEmail({ query: { email_to } })
    return res.data
  }
}

export class PrivateService {
  public static async createUser(options: {
    body?: PrivateUserCreate
    requestBody?: PrivateUserCreate
  }): Promise<UserPublic> {
    const body = options.body || options.requestBody!
    const res = await privateCreateUser({ body })
    return res.data
  }
}

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import deque
from wcwidth import wcswidth

# -----------------------------
# 数据结构
# -----------------------------
@dataclass
class RoundResult:
    round_index: int
    opponent: Optional[str]          # 对手名称；None 代表轮空
    match_point: float               # 大分 (1 / 0.5 / 0)
    small_point: int                 # 小分差 (score_for - score_against)

@dataclass
class TeamStats:
    name: str
    seed: int
    match_points: float = 0.0
    small_points: int = 0
    opponents: List[Optional[str]] = field(default_factory=list)
    round_results: List[RoundResult] = field(default_factory=list)
    buchholz: float = 0.0
    cumulative_rounds: List[float] = field(default_factory=list)
    cumulative_score: float = 0.0
    cop: float = 0.0
    # 直接对比用
    h2h_mp: int = 0
    h2h_sp: int = 0
    h2h_wins: int = 0
    h2h_sp_diff: int = 0

    def add_match(self, rnd: int, opp: Optional[str], score_for: int, score_against: int):
        if opp is None:
            mp = 1.0  # 轮空给 1 分可自行调整
            sp_diff = 0
        else:
            if score_for > score_against:
                mp = 1.0
            elif score_for == score_against:
                mp = 0.5
            else:
                mp = 0.0
            sp_diff = score_for - score_against
        self.match_points += mp
        self.small_points += sp_diff
        self.opponents.append(opp)
        self.round_results.append(RoundResult(rnd, opp, mp, sp_diff))

# -----------------------------
# 解析 / 读取
# -----------------------------
def parse_input(path: str) -> Tuple[Dict[str, TeamStats], List[List[Tuple[str, str, int, int]]]]:
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    i = 0
    team_names: List[str] = []
    while i < len(lines) and not lines[i].isdigit():
        team_names.append(lines[i]); i += 1
    teams: Dict[str, TeamStats] = {n: TeamStats(n, seed+1) for seed, n in enumerate(team_names)}
    rounds: List[List[Tuple[str, str, int, int]]] = []
    while i < len(lines):
        _ = int(lines[i]); i += 1
        matches = []
        while i < len(lines) and not lines[i].isdigit():
            t1, t2, s1, s2 = lines[i].split(',')
            matches.append((t1, t2, int(s1), int(s2)))
            i += 1
        rounds.append(matches)
    return teams, rounds

# -----------------------------
# 统计计算
# -----------------------------
def process_rounds(teams: Dict[str, TeamStats], rounds: List[List[Tuple[str, str, int, int]]]) -> None:
    for rnd_idx, matches in enumerate(rounds, 1):
        for t1, t2, s1, s2 in matches:
            teams[t1].add_match(rnd_idx, t2, s1, s2)
            teams[t2].add_match(rnd_idx, t1, s2, s1)

def compute_buchholz(teams: Dict[str, TeamStats]) -> None:
    for t in teams.values():
        t.buchholz = sum(teams[opp].match_points for opp in t.opponents if opp in teams)

def compute_cumulative_scores(teams: Dict[str, TeamStats]) -> None:
    # 逐队逐轮累计：不依赖 total_rounds，每队按自身已有的对局轮次进行累计
    # 轮空已在 round_results 中以 mp 计入
    for t in teams.values():
        # 按轮次排序，确保累计顺序正确
        results = sorted(t.round_results, key=lambda x: x.round_index)
        t.cumulative_rounds.clear()
        running = 0.0
        for rr in results:
            running += rr.match_point
            t.cumulative_rounds.append(running)
        t.cumulative_score = sum(t.cumulative_rounds)

def compute_cop(teams: Dict[str, TeamStats]) -> None:
    for t in teams.values():
        t.cop = sum(teams[o].cumulative_score for o in t.opponents if o in teams)

def compute_tiebreakers(teams: Dict[str, TeamStats], use_cop: bool = True) -> List[TeamStats]:
    lst = list(teams.values())
    base_key = lambda x: (x.match_points, x.buchholz, x.small_points)
    lst.sort(key=base_key, reverse=True)

    i = 0
    while i < len(lst):
        j = i
        while j < len(lst) and base_key(lst[j]) == base_key(lst[i]):
            j += 1
        group = lst[i:j]
        if len(group) > 1:
            name_set = {g.name for g in group}
            # 计算组内对比
            for g in group:
                h2h_mp = h2h_sp = h2h_wins = h2h_sp_diff = 0
                for rr in g.round_results:
                    if rr.opponent in name_set:
                        h2h_mp += rr.match_point
                        h2h_sp += rr.small_point
                        h2h_sp_diff += rr.small_point
                        if rr.match_point == 1.0:
                            h2h_wins += 1
                g.h2h_mp, g.h2h_sp, g.h2h_wins, g.h2h_sp_diff = h2h_mp, h2h_sp, h2h_wins, h2h_sp_diff
            if use_cop:
                group.sort(key=lambda g: (
                    g.h2h_mp,
                    g.h2h_sp,
                    g.h2h_wins,
                    g.h2h_sp_diff,
                    g.cop,
                    g.cumulative_score,
                    -g.seed
                ), reverse=True)
            else:
                group.sort(key=lambda g: (
                    g.h2h_mp,
                    g.h2h_sp,
                    g.h2h_wins,
                    g.h2h_sp_diff,
                    g.cumulative_score,
                    -g.seed
                ), reverse=True)
            lst[i:j] = group
        i = j
    return lst

# -----------------------------
# 配对算法（Opposite + 浮动）
# -----------------------------
def generate_pairings(sorted_teams: List[TeamStats],
                      previous_rounds: List[List[Tuple[str, str, int, int]]]) -> List[Tuple[str, str]]:
    # 已对阵集合
    played = set()
    for matches in previous_rounds:
        for a, b, _, _ in matches:
            if a and b:
                played.add(tuple(sorted((a, b))))

    # 分组
    groups_map: Dict[float, List[TeamStats]] = {}
    for t in sorted_teams:
        groups_map.setdefault(t.match_points, []).append(t)
    groups: List[List[TeamStats]] = [groups_map[s] for s in sorted(groups_map.keys(), reverse=True)]

    pairings: List[Tuple[str, str]] = []
    float_queue = deque()  # 下浮（FIFO）

    for group in groups:
        next_float = deque()

        # 先处理下浮，与组内“第1名”优先匹配；若第1名已走，尝试下一个仍在的前端成员
        while float_queue and group:
            f = float_queue.popleft()
            matched = False
            # 先尝试组首
            candidate_indices = list(range(len(group)))  # 0,1,2...
            for idx in candidate_indices:
                opponent = group[idx]
                key = tuple(sorted((f.name, opponent.name)))
                if key not in played:
                    pairings.append((f.name, opponent.name))
                    played.add(key)
                    group.pop(idx)
                    matched = True
                    break
            if not matched:
                next_float.append(f)

        # float_queue 里剩余的直接下沉
        while float_queue:
            next_float.append(float_queue.popleft())

        # 组内 opposite pairing（第1 vs 最后）
        while len(group) >= 2:
            first = group[0]
            # 从最后向前找可配对的第一个
            found_idx = -1
            print(first.name)
            for k in range(len(group) - 1, 0, -1):
                key = tuple(sorted((first.name, group[k].name)))
                if key not in played:
                    found_idx = k
                    break
            print(group[found_idx].name if found_idx != -1 else "XX")
            if found_idx == -1:
                # first 无法与组内任何队匹配 -> 下浮
                next_float.append(group.pop(0))
            else:
                second = group[found_idx]
                pairings.append((first.name, second.name))
                played.add(tuple(sorted((first.name, second.name))))
                # 移除 second 和 first
                group.pop(found_idx)
                group.pop(0)

        # 若剩 1 人 -> 下浮
        if len(group) == 1:
            next_float.append(group.pop())

        float_queue = next_float

    # 处理所有剩余下浮队伍（互相尝试配）
    remaining = list(float_queue)
    used = [False] * len(remaining)
    for i in range(len(remaining)):
        if used[i]:
            continue
        t1 = remaining[i]
        matched = False
        for j in range(len(remaining) - 1, i, -1):
            if used[j]:
                continue
            t2 = remaining[j]
            key = tuple(sorted((t1.name, t2.name)))
            if key not in played:
                pairings.append((t1.name, t2.name))
                played.add(key)
                used[i] = used[j] = True
                matched = True
                break
        if not matched:
            pairings.append((t1.name, "BYE"))
            used[i] = True

    return pairings

# -----------------------------
# 输出
# -----------------------------
def align_text(text, width):
    txt = str(text)
    pad = width - wcswidth(txt)
    return txt + " " * max(0, pad)

def print_standings(sorted_teams: List[TeamStats]) -> None:
    headers = ["Rank", "Team", "Score", "Buchholz", "MapDiff", "H2H Score", "H2H MapDiff",  "Cumulative", "Seed"]
    widths  = [5,      28,     7,      9,         8,          10,          12,          12,             5]
    line = "".join(align_text(h, w) for h, w in zip(headers, widths))
    print(line)
    for idx, t in enumerate(sorted_teams, 1):
        vals = [
            idx, t.name, t.match_points, t.buchholz, t.small_points,
            t.h2h_mp, t.h2h_sp_diff, t.cumulative_score, t.seed
        ]
        print("".join(align_text(v, w) for v, w in zip(vals, widths)))

def print_csv_standings(sorted_teams: List[TeamStats]) -> None:
    headers = ["Rank", "Team", "Score", "Buchholz", "MapDiff", "H2H Score", "H2H MapDiff",  "Cumulative", "Seed"]
    widths  = [5,      28,     7,      9,         8,          10,          12,          12,             5]
    line = ",".join(str(h) for h in headers)
    with open("standings.csv", "w", encoding="utf-8") as f:
        f.write(line + "\n")
        for idx, t in enumerate(sorted_teams, 1):
            vals = [
                idx, t.name, t.match_points, t.buchholz, t.small_points,
                t.h2h_mp, t.h2h_sp_diff, t.cumulative_score, t.seed
            ]
            csv_line = ",".join(str(v) for v in vals)
            f.write(csv_line + "\n")

def print_pairings(pairings: List[Tuple[str, str]]) -> None:
    print("\nNext Round Pairings:")
    for a, b in pairings:
        print(f"{a}")
    print("+"*20)  # 分隔
    for a, b in pairings:
        print(f"{b}")
    print("\nNext Round Pairings:")
    for a, b in pairings:
        print(f"{a}")
        print(f"\n"*5)
    print("+"*20)  # 分隔
    for a, b in pairings:
        print(f"{b}")
        print(f"\n"*5)
    

# -----------------------------
# 主流程
# -----------------------------
def run(file_path: str):
    teams, rounds = parse_input(file_path)
    process_rounds(teams, rounds)
    compute_buchholz(teams)
    compute_cumulative_scores(teams)
    compute_cop(teams)
    sorted_teams = compute_tiebreakers(teams, use_cop=False)
    print_standings(sorted_teams)
    pairings = generate_pairings(sorted_teams, rounds)
    print_pairings(pairings)
    print_csv_standings(sorted_teams)

def main():
    import sys
    path = "result.txt" if len(sys.argv) < 2 else sys.argv[1]
    run(path)

if __name__ == "__main__":
    main()

import sys
from collections import defaultdict
from wcwidth import wcswidth
from collections import deque
# 均为了模拟toornment的结果，因为toornment不提供具体小分，以toornment为准
class TeamStats:
    def __init__(self, name):
        self.name = name
        self.match_points = 0
        self.small_points = 0
        self.opponents = []
        self.round_results = []  # (round_index, opponent, match_point, small_point)
        self.seed = None         # 初始种子顺位
    
    def __repr__(self):
        return self.name

def parse_input(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    team_names = []
    i = 0
    while not lines[i].isdigit():
        team_names.append(lines[i])
        i += 1

    team_stats = {}
    for seed, name in enumerate(team_names, start=1):
        team = TeamStats(name)
        team.seed = seed  # 保存初始种子顺位
        team_stats[name] = team

    rounds = []
    while i < len(lines):
        round_index = int(lines[i])
        i += 1
        matches = []
        while i < len(lines) and not lines[i].isdigit():
            team1, team2, score1, score2 = lines[i].split(',')
            matches.append((team1, team2, int(score1), int(score2)))
            i += 1
        rounds.append(matches)

    return team_stats, rounds

def process_rounds(team_stats, rounds):
    round_number = 0
    for matches in rounds:
        round_number += 1
        played = set()
        for team1, team2, score1, score2 in matches:
            played.add(team1)
            played.add(team2)
            win1 = 1 if score1 > score2 else 0
            win2 = 1 if score2 > score1 else 0
            team_stats[team1].match_points += win1
            team_stats[team1].small_points += (score1 - score2)
            team_stats[team1].opponents.append(team2)
            team_stats[team1].round_results.append((round_number, team2, win1, (score1 - score2)))

            team_stats[team2].match_points += win2
            team_stats[team2].small_points += (score2 - score1)
            team_stats[team2].opponents.append(team1)
            team_stats[team2].round_results.append((round_number, team1, win2, (score2 - score1)))

def compute_buchholz(team_stats):
    for team in team_stats.values():
        team.buchholz = sum(team_stats[opp].match_points for opp in team.opponents if opp)

# def compute_cumulative_opponent_points(team_stats, bye_value=0):
#     """计算每支队伍的 Cumulative Opponent Points (COP)，公式化实现。"""
#     for team in team_stats.values():
#         rounds_sorted = sorted(team.round_results, key=lambda x: x[0])
        
#         # 获取每轮对手的最终积分
#         mp_list = []
#         for _, opp, *rest in rounds_sorted:
#             if opp is None:  # 轮空
#                 mp_list.append(bye_value)
#             elif isinstance(opp, str):
#                 mp_list.append(getattr(team_stats.get(opp), "match_points", bye_value))
#             else:
#                 mp_list.append(getattr(opp, "match_points", bye_value))
        
#         R = len(mp_list)
#         # 直接用公式计算 COP
#         team.cop = sum((R - i) * mp for i, mp in enumerate(mp_list))

def compute_cumulative_scores(team_stats, rounds, bye_value_full=1, bye_value_half=0.5):
    """
    根据 FIDE 34E3 定义计算 cumulative score（累计得分表）。
    每个队伍会得到 team.cumulative_score (用于 COP 的计算)。
    """
    # 初始化
    for team in team_stats.values():
        team.cumulative_rounds = []  # 每轮累计大分
        team.cumulative_score = 0.0  # 总累计大分

    # 按轮次计算
    for round_idx, matches in enumerate(rounds, 1):
        for team in team_stats.values():
            # 找到该队伍这一轮的结果
            result = next((r for r in team.round_results if r[0] == round_idx), None)
            if result:
                _, _, mp, _ = result
                if mp == 1:
                    score = 1.0
                elif mp == 0:
                    score = 0.0
                else:
                    score = 0.5  # 支持平局
            else:
                # 没有对局，轮空
                score = 0.0

            prev = team.cumulative_rounds[-1] if team.cumulative_rounds else 0.0
            new_val = prev + score
            team.cumulative_rounds.append(new_val)

    # 计算 cumulative_score
    for team in team_stats.values():
        if len(team.cumulative_rounds) > 1:
            team.cumulative_score = sum(team.cumulative_rounds[:-1])
            # team.cumulative_score = sum(team.cumulative_rounds)
        else:
            team.cumulative_score = sum(team.cumulative_rounds)

        # 调整轮空分数
        for rnd, opp, mp, _ in team.round_results:
            if opp is None:
                if mp == 1:  # 全分轮空
                    team.cumulative_score -= bye_value_full
                elif mp == 0.5:  # 半分轮空
                    team.cumulative_score -= bye_value_half


def compute_cop(team_stats):
    """
    根据 FIDE 34E9 定义计算 COP（Cumulative scores of opposition）。
    COP = 所有对手 cumulative_score 之和
    """
    for team in team_stats.values():
        cop = 0.0
        for opp in team.opponents:
            if opp and opp in team_stats:
                cop += team_stats[opp].cumulative_score
        team.cop = cop

def compute_tiebreakers(team_stats, COP = True):
    sorted_teams = list(team_stats.values())

    def tiebreak_key(team):
        return (
            team.match_points,   # 总大分积分
            team.buchholz,       # 布赫霍尔茨
            team.small_points,   # 总小分
        )

    sorted_teams.sort(key=tiebreak_key, reverse=True)

    i = 0
    while i < len(sorted_teams):
        j = i
        while j < len(sorted_teams) and tiebreak_key(sorted_teams[i]) == tiebreak_key(sorted_teams[j]):
            j += 1

        group = sorted_teams[i:j]
        h2h_stats = {}

        if j - i > 1:
            for team in group:
                h2h_mp = 0
                h2h_sp = 0
                h2h_wins = 0
                h2h_sp_diff = 0
                for rnd, opp, mp, sp in team.round_results:
                    if opp in [t.name for t in group]:
                        h2h_mp += mp
                        h2h_sp += sp
                        if mp == 1:
                            h2h_wins += 1
                        h2h_sp_diff += sp
                h2h_stats[team.name] = (h2h_mp, h2h_sp, h2h_wins, h2h_sp_diff)
            if COP:
                group.sort(
                    key=lambda t: (
                        h2h_stats[t.name][0],  # H2H 大分
                        h2h_stats[t.name][1],  # H2H 小分
                        h2h_stats[t.name][2],  # 规则 4：大分胜场数
                        h2h_stats[t.name][3],  # 规则 5：小分差
                        t.cumulative_score,    # 累计对手分
                        -t.seed                # 初始种子顺位（seed 越小优先级越高）
                    ),
                    reverse=True
                )
            else:
                group.sort(
                    key=lambda t: (
                        h2h_stats[t.name][0],  # H2H 大分
                        h2h_stats[t.name][1],  # H2H 小分
                        h2h_stats[t.name][2],  # 规则 4：大分胜场数
                        h2h_stats[t.name][3],  # 规则 5：小分差
                        -t.seed                # 初始种子顺位（seed 越小优先级越高）
                    ),
                    reverse=True
                )
        else:
            team = group[0]
            h2h_stats[team.name] = (-1, -1, -1, -1)

        sorted_teams[i:j] = group
        for team in group:
            team.h2h_mp, team.h2h_sp, team.h2h_wins, team.h2h_sp_diff = h2h_stats[team.name]
        i = j

    return sorted_teams

def align_text(text, width):
    """对齐中英文混合字符串"""
    text = str(text)
    display_width = wcswidth(text)
    pad = width - display_width
    return text + " " * max(0, pad)

def print_standings(sorted_teams):
    headers = ["Rank", "Team", "Score", "Buchholz", "Map Diff", "H2H Score", "H2H MapDiff", "Cumulative", "seed"]
    widths = [5, 30, 10, 10, 10, 12, 15, 12, 6]

    header_line = "".join(align_text(h, w) for h, w in zip(headers, widths))
    print(header_line)

    for idx, team in enumerate(sorted_teams, 1):
        h2h_mp = getattr(team, 'h2h_mp', 0)
        h2h_sp = getattr(team, 'h2h_sp', 0)
        values = [
            idx, team.name, team.match_points, team.buchholz,
            team.small_points, h2h_mp, h2h_sp, team.cumulative_score, team.seed
        ]
        line = "".join(align_text(v, w) for v, w in zip(values, widths))
        print(line)
    # Output to csv:
    with open("standings.csv", "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for idx, team in enumerate(sorted_teams, 1):
            h2h_mp = getattr(team, 'h2h_mp', 0)
            h2h_sp = getattr(team, 'h2h_sp', 0)
            values = [
                idx, team.name, team.match_points, team.buchholz,
                team.small_points, h2h_mp, h2h_sp, team.cumulative_score, team.seed
            ]
            f.write(",".join(map(str, values)) + "\n")
def generate_pairings(sorted_teams, previous_rounds):
    """
    生成下一轮对阵（Opposite pairing，避免重复对局）。
    规则重点：
      - 组内按顺序第1名配最后一名（opposite pairing）。
      - 上组下浮的队列（FIFO）优先匹配本组的第1名（若第1名已被配走则匹配组内第一个可配对队伍）。
      - 若队伍在当前组无法配对，则下浮到下一组（可能产生多个下浮队伍）。
      - 所有组处理完后，尝试在剩余下浮队伍间配对；仍无法配对的则轮空（BYE）。
    输入：
      - sorted_teams: 按当前排名（从高到低）排序的 TeamStats 列表
      - previous_rounds: 历史对局，list of rounds，每轮为[(team1, team2, score1, score2), ...]
    返回：
      - pairings: list of (teamA_name, teamB_name)；若轮空则为 ("TeamName", "BYE")
    """
    from collections import deque

    # 构建已对阵集合（名字排序的 tuple），用于快速查重
    played_pairs = set()
    for matches in previous_rounds:
        for t1, t2, _, _ in matches:
            if t1 and t2:
                played_pairs.add(tuple(sorted([t1, t2])))

    # 按得分分组（保持 sorted_teams 的组内次序，高分在前）
    score_groups = {}
    for team in sorted_teams:
        score_groups.setdefault(team.match_points, []).append(team)

    groups = [score_groups[s][:] for s in sorted(score_groups.keys(), reverse=True)]

    pairings = []
    carry_queue = deque()  # FIFO，下浮队列（来自上组未能配对的队，先到先匹配本组第1名）

    # 逐组处理（高分到低分）
    for group in groups:
        # group 是列表，保持原有次序（第0项为组内第1名）
        next_carry = deque()

        # 1) 优先尝试为 carry_queue 中的每个下浮队伍找本组对手（优先第1名）
        while carry_queue and group:
            floater = carry_queue.popleft()
            matched = False
            # 优先尝试组首（index 0），然后往后寻找第一个未曾对阵者
            for idx, candidate in enumerate(group):
                key = tuple(sorted([floater.name, candidate.name]))
                if key not in played_pairs:
                    pairings.append((floater.name, candidate.name))
                    played_pairs.add(key)
                    group.pop(idx)
                    matched = True
                    break
            if not matched:
                # 本组无人可配，继续下沉
                next_carry.append(floater)

        # 若 carry_queue 中还有未处理者（因为 group 为空），全部下沉
        while carry_queue:
            next_carry.append(carry_queue.popleft())

        # 2) 组内按 opposite pairing（第1 vs 最后）配对，遇到曾对过的尽量在尾部寻找可配对者
        # 使用while循环保持对 group 动态修改
        while len(group) >= 2:
            t1 = group[0]  # 组内第1名
            found = False
            # 从尾部向前找第一个可配对的
            for k in range(len(group)-1, 0, -1):
                t2 = group[k]
                key = tuple(sorted([t1.name, t2.name]))
                if key not in played_pairs:
                    pairings.append((t1.name, t2.name))
                    played_pairs.add(key)
                    # 移除已配对的两个：先移后面的再移前面的
                    group.pop(k)
                    group.pop(0)
                    found = True
                    break
            if not found:
                # t1 与组内所有人都已对过 -> 下浮
                next_carry.append(group.pop(0))

        # 3) 若组内剩1人，则该人下浮
        if len(group) == 1:
            next_carry.append(group.pop(0))

        # 准备进入下一组
        carry_queue = next_carry

    # 所有组处理完毕，尝试在剩余的下浮队伍间配对（同样避免重复对局）
    remaining = list(carry_queue)
    unmatched = []
    used = [False] * len(remaining)

    for i in range(len(remaining)):
        if used[i]:
            continue
        t1 = remaining[i]
        found = False
        # 从后向前找可配对者
        for j in range(len(remaining)-1, i, -1):
            if used[j]:
                continue
            t2 = remaining[j]
            key = tuple(sorted([t1.name, t2.name]))
            if key not in played_pairs:
                pairings.append((t1.name, t2.name))
                played_pairs.add(key)
                used[i] = used[j] = True
                found = True
                break
        if not found:
            unmatched.append(t1)

    # 仍有无法配对的队伍，给出 BYE（一般最多会有1个，若有多个则都轮空——实际比赛规则可自行调整）
    for t in unmatched:
        pairings.append((t.name, "BYE"))

    return pairings


def main(file_path):
    team_stats, rounds = parse_input(file_path)
    process_rounds(team_stats, rounds)
    compute_buchholz(team_stats)
    compute_cumulative_scores(team_stats, rounds)
    compute_cop(team_stats)
    sorted_teams = compute_tiebreakers(team_stats)
    print_standings(sorted_teams)
    pairings = generate_pairings(sorted_teams, rounds)
    print("\nNext Round Pairings:")
    # 打印结果
    for a in pairings:
        print(f"{a[0]}\t")
    print("="*160)
    for a, b in pairings:
        print(f"{b}\t")
    
    # sorted_teams = compute_tiebreakers(team_stats, COP=False)
    # print_standings(sorted_teams)

if __name__ == "__main__":
    main("result.txt")

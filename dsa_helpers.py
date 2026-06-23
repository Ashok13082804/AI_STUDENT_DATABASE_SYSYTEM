import heapq

# ==========================================
# 1. Binary Search Tree (BST) for Student ID
# ==========================================
class BSTNode:
    def __init__(self, key, value):
        self.key = key       # Student ID (String or Int)
        self.value = value   # Student dict
        self.left = None
        self.right = None

class StudentBST:
    def __init__(self):
        self.root = None

    def insert(self, key, value):
        if not self.root:
            self.root = BSTNode(key, value)
        else:
            self._insert(self.root, key, value)

    def _insert(self, node, key, value):
        if key < node.key:
            if not node.left:
                node.left = BSTNode(key, value)
            else:
                self._insert(node.left, key, value)
        elif key > node.key:
            if not node.right:
                node.right = BSTNode(key, value)
            else:
                self._insert(node.right, key, value)
        else:
            node.value = value # Update

    def search(self, key):
        """Returns (student_value, path_taken)"""
        path = []
        result = self._search(self.root, key, path)
        return result, path

    def _search(self, node, key, path):
        if not node:
            path.append("None (Not Found)")
            return None
        
        path.append(node.key)
        if key == node.key:
            return node.value
        elif key < node.key:
            return self._search(node.left, key, path)
        else:
            return self._search(node.right, key, path)


# ==========================================
# 2. Heap (Max-Heap) for Top-K Rankings
# ==========================================
class TopStudentsHeap:
    @staticmethod
    def get_top_k(students_list, k=5):
        """
        Input: list of student dictionaries, each with 'cgpa' and 'name'
        Output: top k students using a heap (using negative values for max-heap)
        """
        heap = []
        for s in students_list:
            cgpa = float(s.get('cgpa') or 0.0)
            # Store in heap as (-cgpa, name, s) to retrieve highest CGPA first
            heapq.heappush(heap, (-cgpa, s.get('name', 'Unknown'), s))
        
        results = []
        count = min(k, len(heap))
        for _ in range(count):
            neg_cgpa, name, s = heapq.heappop(heap)
            results.append({
                "id": s.get('id'),
                "name": name,
                "cgpa": -neg_cgpa,
                "department": s.get('department'),
                "year": s.get('year')
            })
        return results


# ==========================================
# 3. Directed Graph for Course Prerequisites
# ==========================================
class CourseGraph:
    def __init__(self):
        self.adj_list = {}

    def add_course(self, course_id):
        if course_id not in self.adj_list:
            self.adj_list[course_id] = []

    def add_prerequisite(self, course_id, prereq_id):
        self.add_course(course_id)
        self.add_course(prereq_id)
        if prereq_id not in self.adj_list[course_id]:
            self.adj_list[course_id].append(prereq_id)

    def has_cycle(self):
        """Detect cycle in graph using DFS to prevent circular dependencies."""
        visited = {} # None: unvisited, 1: visiting, 2: visited
        for course in self.adj_list:
            visited[course] = 0
            
        def dfs(node):
            visited[node] = 1 # Visiting
            for neighbor in self.adj_list.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    return True # Cycle detected
                if visited.get(neighbor, 0) == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2 # Visited
            return False

        for course in self.adj_list:
            if visited[course] == 0:
                if dfs(course):
                    return True
        return False

    def get_prerequisite_path(self, course_id):
        """DFS to find all nested prerequisites for a course."""
        visited = set()
        path = []
        
        def dfs(node):
            visited.add(node)
            for neighbor in self.adj_list.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            path.append(node)
            
        dfs(course_id)
        # The course itself is at the end, so prerequisites are everything before
        return path[:-1]

    def topological_sort(self):
        """Topological sort using Kahn's algorithm or DFS."""
        visited = set()
        stack = []

        def dfs(node):
            visited.add(node)
            for neighbor in self.adj_list.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            stack.append(node)

        for course in self.adj_list:
            if course not in visited:
                dfs(course)
        
        return stack # Returns courses in topological order (bottom-up prerequisites first)


# ==========================================================
# 4. Dynamic Programming (DP) Timetable Clash Optimizer
# ==========================================================
class TimetableOptimizer:
    @staticmethod
    def convert_time_to_minutes(time_str):
        """Converts 'HH:MM' to minutes from midnight."""
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def schedule_clash_free(classes):
        """
        Inputs: list of class dicts with keys:
                {'id', 'course_id', 'day', 'start_time', 'end_time', 'room'}
        Output: a list of successfully scheduled clash-free classes, and conflicts.
        
        Algorithm: Dynamic Programming Interval Scheduling.
        Sort courses by end time, and use DP to find the maximum set of non-overlapping sessions
        per room, per day.
        """
        # Group classes by day and room
        grouped = {}
        for c in classes:
            day = c['day']
            room = c['room']
            key = (day, room)
            if key not in grouped:
                grouped[key] = []
            
            # Parse start and end times
            c['start_min'] = TimetableOptimizer.convert_time_to_minutes(c['start_time'])
            c['end_min'] = TimetableOptimizer.convert_time_to_minutes(c['end_time'])
            grouped[key].append(c)

        scheduled = []
        conflicted = []

        for key, day_room_classes in grouped.items():
            # Sort by end time
            day_room_classes.sort(key=lambda x: x['end_min'])
            
            n = len(day_room_classes)
            if n == 0:
                continue

            # DP array: dp[i] stores the maximum number of non-overlapping classes ending at index i
            dp = [1] * n
            parent = [-1] * n # To reconstruct the schedule

            # Find the largest non-overlapping previous class
            for i in range(1, n):
                for j in range(i - 1, -1, -1):
                    # Check if class j ends before class i starts
                    if day_room_classes[j]['end_min'] <= day_room_classes[i]['start_min']:
                        if dp[j] + 1 > dp[i]:
                            dp[i] = dp[j] + 1
                            parent[i] = j
                        break # Since sorted by end_min, first overlap-free j is usually optimal
                
                # Check option of not scheduling class i at all
                # (if scheduling previous set is better than including class i)
                # But here we just want to select the optimal subset of classes.

            # Find index of max value in dp
            max_idx = dp.index(max(dp))
            
            # Reconstruct optimal scheduled set
            optimal_set_indices = []
            curr = max_idx
            while curr != -1:
                optimal_set_indices.append(curr)
                curr = parent[curr]
            
            optimal_set_indices.reverse()
            
            # Add to scheduled and conflicted lists
            for idx in range(n):
                c = day_room_classes[idx]
                # Clean up temporary fields
                clean_c = c.copy()
                clean_c.pop('start_min', None)
                clean_c.pop('end_min', None)
                
                if idx in optimal_set_indices:
                    scheduled.append(clean_c)
                else:
                    clean_c['conflict_reason'] = f"Time overlap in Room {c['room']} on {c['day']}"
                    conflicted.append(clean_c)

        return scheduled, conflicted

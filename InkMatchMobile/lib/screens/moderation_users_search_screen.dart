import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import 'moderation_user_screen.dart';

class ModerationUsersSearchScreen extends StatefulWidget {
  const ModerationUsersSearchScreen({super.key});

  static const route = '/moderation/users';

  @override
  State<ModerationUsersSearchScreen> createState() =>
      _ModerationUsersSearchScreenState();
}

class _ModerationUsersSearchScreenState
    extends State<ModerationUsersSearchScreen> {
  final _api = ApiClient.defaultClient();
  final _qCtrl = TextEditingController();

  bool _loading = false;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  String _role = 'all';
  String _verified = 'all';

  String? get _token => AppSession.instance.accessToken;
  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  @override
  void initState() {
    super.initState();
    _search();
  }

  @override
  void dispose() {
    _qCtrl.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final query = <String, String>{'limit': '100', 'offset': '0'};
      if (_qCtrl.text.trim().isNotEmpty) query['q'] = _qCtrl.text.trim();
      var roleForQuery = _role;
      if (_verified != 'all' && roleForQuery == 'all') {
        roleForQuery = 'master';
      }
      if (roleForQuery != 'all') query['role'] = roleForQuery;
      if (_verified == 'yes') query['is_verified'] = 'true';
      if (_verified == 'no') query['is_verified'] = 'false';

      final res = await _api.getJson(
        '/moderation/users',
        accessToken: _token,
        query: query,
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }

      final data = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList();
      setState(() {
        _items = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _t(
          isRu,
          'Ошибка поиска: $e',
          'Search failed: $e',
        );
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(
          _t(
            isRu,
            'Поиск пользователей',
            'Users search',
          ),
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                TextField(
                  controller: _qCtrl,
                  decoration: InputDecoration(
                    labelText: _t(
                      isRu,
                      'Ник / email / телефон',
                      'Nickname / email / phone',
                    ),
                    suffixIcon: IconButton(
                      onPressed: _search,
                      icon: const Icon(Icons.search),
                    ),
                  ),
                  onSubmitted: (_) => _search(),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    SizedBox(
                      width: MediaQuery.of(context).size.width > 520
                          ? (MediaQuery.of(context).size.width - 40) / 2
                          : double.infinity,
                      child: DropdownButtonFormField<String>(
                        initialValue: _role,
                        decoration: InputDecoration(
                          labelText: _t(
                            isRu,
                            'Роль',
                            'Role',
                          ),
                        ),
                        items: [
                          DropdownMenuItem(
                            value: 'all',
                            child: Text(_t(isRu, 'Все', 'All')),
                          ),
                          DropdownMenuItem(
                            value: 'client',
                            child: Text(
                              _t(
                                isRu,
                                'Клиент',
                                'Client',
                              ),
                            ),
                          ),
                          DropdownMenuItem(
                            value: 'master',
                            child: Text(
                              _t(
                                isRu,
                                'Мастер',
                                'Master',
                              ),
                            ),
                          ),
                          DropdownMenuItem(
                            value: 'moderator',
                            child: Text(
                              _t(
                                isRu,
                                'Модератор',
                                'Moderator',
                              ),
                            ),
                          ),
                        ],
                        onChanged: (v) => setState(() => _role = v ?? 'all'),
                      ),
                    ),
                    SizedBox(
                      width: MediaQuery.of(context).size.width > 520
                          ? (MediaQuery.of(context).size.width - 40) / 2
                          : double.infinity,
                      child: DropdownButtonFormField<String>(
                        initialValue: _verified,
                        decoration: InputDecoration(
                          labelText: _t(
                            isRu,
                            'Верификация (только мастера)',
                            'Verification (masters only)',
                          ),
                        ),
                        items: [
                          DropdownMenuItem(
                            value: 'all',
                            child: Text(
                              _t(isRu, 'Любой', 'All'),
                            ),
                          ),
                          DropdownMenuItem(
                            value: 'yes',
                            child: Text(
                              _t(
                                isRu,
                                'Только верифицированные',
                                'Verified only',
                              ),
                            ),
                          ),
                          DropdownMenuItem(
                            value: 'no',
                            child: Text(
                              _t(
                                isRu,
                                'Без верификации',
                                'Not verified',
                              ),
                            ),
                          ),
                        ],
                        onChanged: (v) =>
                            setState(() => _verified = v ?? 'all'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _search,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accent,
                      foregroundColor: Colors.white,
                    ),
                    child: Text(
                      _t(
                        isRu,
                        'Применить фильтры',
                        'Apply filters',
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(child: Text(_error!))
                : ListView.separated(
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      return ListTile(
                        leading: CircleAvatar(
                          backgroundImage:
                              (item['avatar_url']?.toString().isNotEmpty ??
                                  false)
                              ? NetworkImage(item['avatar_url'].toString())
                              : null,
                          child:
                              (item['avatar_url']?.toString().isNotEmpty ??
                                  false)
                              ? null
                              : const Icon(Icons.person),
                        ),
                        title: Text(item['nickname']?.toString() ?? '-'),
                        subtitle: Text(
                          '${item['email'] ?? item['phone'] ?? '-'}\n'
                          '${_t(isRu, 'Роль', 'Role')}: ${item['role']} | '
                          '${_t(isRu, 'Верифицирован', 'Verified')}: ${item['is_verified']}',
                        ),
                        isThreeLine: true,
                        onTap: () => Navigator.pushNamed(
                          context,
                          ModerationUserScreen.route,
                          arguments: ModerationUserScreenArgs(
                            userId: item['id'].toString(),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

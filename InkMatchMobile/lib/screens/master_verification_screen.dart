import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class MasterVerificationScreen extends StatefulWidget {
  const MasterVerificationScreen({super.key});

  static const route = '/master-verification';

  @override
  State<MasterVerificationScreen> createState() =>
      _MasterVerificationScreenState();
}

class _MasterVerificationScreenState extends State<MasterVerificationScreen> {
  final _api = ApiClient.defaultClient();
  final _firstNameCtrl = TextEditingController();
  final _secondNameCtrl = TextEditingController();
  final _lastNameCtrl = TextEditingController();
  final _patronymicCtrl = TextEditingController();
  final _birthDateCtrl = TextEditingController();
  final _citizenshipCtrl = TextEditingController();
  final _titleCtrl = TextEditingController();
  final _issuerCtrl = TextEditingController();
  final _issuedDateCtrl = TextEditingController();

  String _documentType = 'certificate';
  bool _loading = true;
  bool _saving = false;
  String? _error;
  Map<String, dynamic>? _request;

  String? get _token => AppSession.instance.accessToken;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _firstNameCtrl.dispose();
    _secondNameCtrl.dispose();
    _lastNameCtrl.dispose();
    _patronymicCtrl.dispose();
    _birthDateCtrl.dispose();
    _citizenshipCtrl.dispose();
    _titleCtrl.dispose();
    _issuerCtrl.dispose();
    _issuedDateCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await _api.getJson(
        '/profiles/me/verification',
        accessToken: _token,
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }
      final payload = jsonDecode(res.body) as Map<String, dynamic>;
      final personal = payload['personal_data'] as Map<String, dynamic>?;
      if (personal != null) {
        _firstNameCtrl.text = personal['first_name']?.toString() ?? '';
        _secondNameCtrl.text = personal['second_name']?.toString() ?? '';
        _lastNameCtrl.text = personal['last_name']?.toString() ?? '';
        _patronymicCtrl.text = personal['patronymic']?.toString() ?? '';
        _birthDateCtrl.text = personal['birth_date']?.toString() ?? '';
        _citizenshipCtrl.text = personal['citizenship']?.toString() ?? '';
      }
      setState(() {
        _request = payload;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<bool> _savePersonalData() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    if (_firstNameCtrl.text.trim().isEmpty ||
        _lastNameCtrl.text.trim().isEmpty ||
        _birthDateCtrl.text.trim().isEmpty) {
      _showMessage(
        isRu
            ? 'Заполните имя, фамилию и дату рождения'
            : 'Fill first name, last name and birth date',
      );
      return false;
    }

    final res = await _api.putJson('/profiles/me/verification/personal-data', {
      'first_name': _firstNameCtrl.text.trim(),
      'second_name': _emptyToNull(_secondNameCtrl.text),
      'last_name': _lastNameCtrl.text.trim(),
      'patronymic': _emptyToNull(_patronymicCtrl.text),
      'birth_date': _birthDateCtrl.text.trim(),
      'citizenship': _emptyToNull(_citizenshipCtrl.text),
    }, accessToken: _token);

    if (res.statusCode != 200) {
      _showMessage('${res.statusCode}: ${res.body}');
      return false;
    }
    _request = jsonDecode(res.body) as Map<String, dynamic>;
    return true;
  }

  Future<void> _pickAndUploadDocument({required String documentType}) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    setState(() => _saving = true);
    try {
      final saved = await _savePersonalData();
      if (!saved) return;

      final result = await FilePicker.platform.pickFiles(
        allowMultiple: false,
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
      );
      final path = result?.files.single.path;
      if (path == null) return;

      final uploadRes = await _api.postMultipart(
        '/profiles/me/verification/documents',
        file: File(path),
        fieldName: 'file',
        accessToken: _token,
        fields: {
          'document_type': documentType,
          if (_needsTitle(documentType) && _titleCtrl.text.trim().isNotEmpty)
            'title': _titleCtrl.text.trim(),
          if (_issuerCtrl.text.trim().isNotEmpty)
            'issuer': _issuerCtrl.text.trim(),
          if (_issuedDateCtrl.text.trim().isNotEmpty)
            'issued_date': _issuedDateCtrl.text.trim(),
        },
      );
      if (uploadRes.statusCode != 201) {
        _showMessage('${uploadRes.statusCode}: ${uploadRes.body}');
        return;
      }
      if (documentType != 'passport') {
        _titleCtrl.clear();
      }
      _issuerCtrl.clear();
      _issuedDateCtrl.clear();
      await _load();
      _showMessage(
        isRu ? 'Документ добавлен' : 'Document added',
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _submit() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    setState(() => _saving = true);
    try {
      final saved = await _savePersonalData();
      if (!saved) return;
      final docs = (_request?['documents'] as List<dynamic>? ?? const []);
      if (docs.isEmpty) {
        _showMessage(
          isRu
              ? 'Добавьте хотя бы один документ'
              : 'Add at least one document',
        );
        return;
      }
      final res = await _api.postJson(
        '/profiles/me/verification/submit',
        {},
        accessToken: _token,
      );
      if (res.statusCode != 200) {
        _showMessage('${res.statusCode}: ${res.body}');
        return;
      }
      await _load();
      _showMessage(
        isRu
            ? 'Заявка отправлена модераторам'
            : 'Request sent to moderators',
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _skip() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isRu
              ? 'Пропустить верификацию?'
              : 'Skip verification?',
        ),
        content: Text(
          isRu
              ? 'Вы сможете пройти верификацию позже. В профиле будет отображаться напоминание.'
              : 'You can verify later. A reminder will appear in your profile.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(isRu ? 'Отмена' : 'Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(isRu ? 'Пропустить' : 'Skip'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _saving = true);
    try {
      final res = await _api.postJson(
        '/profiles/me/verification/skip',
        {},
        accessToken: _token,
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        _showMessage('${res.statusCode}: ${res.body}');
        return;
      }
      _showMessage(
        isRu
            ? 'Верификация пропущена'
            : 'Verification skipped',
      );
      if (Navigator.canPop(context)) {
        Navigator.pop(context, true);
      } else {
        Navigator.pushNamedAndRemoveUntil(
          context,
          '/demo-feed',
          (route) => false,
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _emptyToNull(String value) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  void _showMessage(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  String _documentTypeLabel(String value, bool isRu) {
    return switch (value) {
      'passport' => isRu ? 'Документ личности' : 'Identity document',
      'certificate' => isRu ? 'Сертификат' : 'Certificate',
      'diploma' => isRu ? 'Диплом' : 'Diploma',
      'award' => isRu ? 'Награда' : 'Award',
      _ => isRu ? 'Другое' : 'Other',
    };
  }

  bool _needsTitle(String value) {
    return value == 'certificate' || value == 'award' || value == 'other';
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final status = _request?['status']?.toString() ?? 'draft';
    final docs = (_request?['documents'] as List<dynamic>? ?? const [])
        .cast<Map<String, dynamic>>();
    final locked =
        status == 'submitted' || status == 'in_review' || status == 'approved';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          isRu
              ? 'Верификация мастера'
              : 'Master verification',
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _StatusPanel(status: status, isRu: isRu),
                const SizedBox(height: 12),
                _SectionTitle(
                  text: isRu ? 'Личные данные' : 'Personal data',
                ),
                _field(isRu ? 'Имя' : 'First name', _firstNameCtrl, locked),
                _field(
                  isRu ? 'Фамилия' : 'Last name',
                  _lastNameCtrl,
                  locked,
                ),
                _field(
                  isRu ? 'Отчество' : 'Patronymic',
                  _patronymicCtrl,
                  locked,
                ),
                _field(
                  isRu ? 'Второе имя' : 'Second name',
                  _secondNameCtrl,
                  locked,
                ),                _field(
                  isRu ? '???? ????????' : 'Birth date',
                  _birthDateCtrl,
                  locked,
                  readOnly: true,
                  onTap: locked
                      ? null
                      : () async {
                          final initial =
                              DateTime.tryParse(_birthDateCtrl.text.trim()) ??
                              DateTime.now();
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: initial,
                            firstDate: DateTime(1900),
                            lastDate: DateTime.now(),
                            helpText:
                                isRu ? '???????? ???? ????????' : 'Pick birth date',
                          );
                          if (picked == null || !mounted) return;
                          setState(() {
                            _birthDateCtrl.text =
                                '${picked.year.toString().padLeft(4, '0')}-'
                                '${picked.month.toString().padLeft(2, '0')}-'
                                '${picked.day.toString().padLeft(2, '0')}';
                          });
                        },
                ),
                _field(
                  isRu ? 'Гражданство' : 'Citizenship',
                  _citizenshipCtrl,
                  locked,
                ),
                const SizedBox(height: 16),
                _SectionTitle(
                  text: isRu ? 'Документ личности' : 'Identity document',
                ),
                if (!locked) ...[
                  OutlinedButton.icon(
                    onPressed: _saving
                        ? null
                        : () =>
                              _pickAndUploadDocument(documentType: 'passport'),
                    icon: const Icon(Icons.badge_outlined),
                    label: Text(
                      isRu ? 'Загрузить документ' : 'Upload identity document',
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                _SectionTitle(
                  text: isRu
                      ? 'Дополнительные документы'
                      : 'Optional documents',
                ),
                if (!locked) ...[
                  DropdownButtonFormField<String>(
                    initialValue: _documentType,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Тип документа'
                          : 'Document type',
                    ),
                    items: const ['certificate', 'diploma', 'award', 'other']
                        .map(
                          (value) => DropdownMenuItem(
                            value: value,
                            child: Text(_documentTypeLabel(value, isRu)),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => _documentType = value ?? 'certificate'),
                  ),
                  if (_needsTitle(_documentType))
                    _field(
                      isRu ? 'Название' : 'Title',
                      _titleCtrl,
                      false,
                    ),
                  _field(
                    isRu ? 'Кем выдан' : 'Issuer',
                    _issuerCtrl,
                    false,
                  ),
                  _field(
                    isRu
                        ? 'Дата выдачи: YYYY-MM-DD'
                        : 'Issued date: YYYY-MM-DD',
                    _issuedDateCtrl,
                    false,
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _saving
                        ? null
                        : () => _pickAndUploadDocument(
                            documentType: _documentType,
                          ),
                    icon: const Icon(Icons.attach_file),
                    label: Text(
                      isRu
                          ? 'Добавить документ'
                          : 'Add document',
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                if (docs.isEmpty)
                  Text(
                    isRu
                        ? 'Файлы еще не добавлены'
                        : 'No files yet',
                  )
                else
                  ...docs.map(
                    (doc) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.description_outlined),
                      title: Text(
                        doc['title']?.toString().isNotEmpty == true
                            ? doc['title'].toString()
                            : _documentTypeLabel(
                                doc['document_type'].toString(),
                                isRu,
                              ),
                      ),
                      subtitle: Text(
                        doc['issuer']?.toString() ??
                            doc['file_type'].toString(),
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                if (!locked)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ElevatedButton.icon(
                        onPressed: _saving ? null : _submit,
                        icon: const Icon(Icons.verified_user_outlined),
                        label: Text(
                          isRu
                              ? 'Отправить на проверку'
                              : 'Submit for review',
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.accent,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: _saving ? null : _skip,
                        icon: const Icon(Icons.close),
                        label: Text(isRu ? 'Пропустить' : 'Skip'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                      ),
                    ],
                  ),
                if (_saving)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Center(child: CircularProgressIndicator()),
                  ),
              ],
            ),
    );
  }

  Widget _field(
    String label,
    TextEditingController controller,
    bool disabled, {
    VoidCallback? onTap,
    bool readOnly = false,
    TextInputType? keyboardType,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextField(
        controller: controller,
        enabled: !disabled,
        readOnly: readOnly,
        keyboardType: keyboardType,
        onTap: onTap,
        decoration: InputDecoration(labelText: label),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        text,
        style: TextStyle(
          fontFamily: AppTypography.headerFont(locale),
          fontSize: 22,
          color: AppColors.ink,
        ),
      ),
    );
  }
}

class _StatusPanel extends StatelessWidget {
  const _StatusPanel({required this.status, required this.isRu});

  final String status;
  final bool isRu;

  @override
  Widget build(BuildContext context) {
    final text = switch (status) {
      'approved' =>
        isRu ? 'Профиль верифицирован' : 'Profile verified',
      'submitted' || 'in_review' =>
        isRu ? 'Заявка на проверке' : 'Request is under review',
      'rejected' =>
        isRu
            ? 'Заявка отклонена. Можно отправить заново'
            : 'Rejected. You can submit again',
      _ =>
        isRu
            ? 'Заполните данные и прикрепите документы'
            : 'Fill data and attach documents',
    };
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.ink.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text),
    );
  }
}

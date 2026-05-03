import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'app_config.dart';

class ApiClient {
  ApiClient(this.baseUrl);

  factory ApiClient.defaultClient() => ApiClient(AppConfig.apiBaseUrl);

  final String baseUrl;

  Future<http.Response> postJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    return http.post(
      uri,
      headers: _headers(accessToken),
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 12));
  }

  Future<http.Response> getJson(
    String path, {
    String? accessToken,
    Map<String, String>? query,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    return http.get(uri, headers: _headers(accessToken)).timeout(const Duration(seconds: 12));
  }

  Future<http.Response> putJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    return http.put(
      uri,
      headers: _headers(accessToken),
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 12));
  }

  Future<http.Response> patchJson(
    String path,
    Map<String, dynamic> body, {
    String? accessToken,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    return http.patch(
      uri,
      headers: _headers(accessToken),
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 12));
  }

  Future<http.Response> deleteJson(String path, {String? accessToken}) async {
    final uri = Uri.parse('$baseUrl$path');
    return http.delete(uri, headers: _headers(accessToken)).timeout(const Duration(seconds: 12));
  }

  Future<http.Response> postMultipart(
    String path, {
    required File file,
    required String fieldName,
    MediaType? contentType,
    String? accessToken,
    Map<String, String>? fields,
  }) async {
    final uri = Uri.parse('$baseUrl$path');
    final request = http.MultipartRequest('POST', uri)
      ..headers.addAll(_multipartHeaders(accessToken))
      ..fields.addAll(fields ?? <String, String>{})
      ..files.add(
        await http.MultipartFile.fromPath(
          fieldName,
          file.path,
          contentType: contentType,
        ),
      );

    final streamed = await request.send();
    return http.Response.fromStream(streamed);
  }

  Map<String, String> _headers(String? accessToken) {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (accessToken != null && accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $accessToken';
    }
    return headers;
  }

  Map<String, String> _multipartHeaders(String? accessToken) {
    final headers = <String, String>{};
    if (accessToken != null && accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $accessToken';
    }
    return headers;
  }
}

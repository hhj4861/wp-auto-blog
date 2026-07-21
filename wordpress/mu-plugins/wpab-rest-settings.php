<?php
/**
 * Plugin Name: WPAB REST Settings Bridge
 * Description: 댓글 승인 정책 옵션(comment_moderation, comment_previously_approved)을
 *              REST /wp/v2/settings 에 노출해 파이프라인이 원격으로 설정할 수 있게 한다.
 * Author: wp-auto-blog
 * Version: 1.0.0
 *
 * Install: wp-content/mu-plugins/ 에 업로드 (활성화 절차 불필요).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action( 'init', function () {
	$options = array(
		'comment_moderation',           // '1' = 모든 댓글 수동 승인 대기, '0' = 자동 승인
		'comment_previously_approved',  // '1' = 첫 댓글만 대기(재승인자 자동), '0' = 이력 무관
	);

	foreach ( $options as $option ) {
		register_setting( 'discussion', $option, array(
			'show_in_rest' => true,
			'type'         => 'string',
			'description'  => 'WPAB remote comment approval policy',
		) );
	}
} );
